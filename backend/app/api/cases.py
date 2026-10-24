import json
import secrets
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.models import Case, FamilyCluster, Band, NotificationAttempt, User, AuditLog, ScanLog
from backend.app.schemas.schemas import (
    CaseResponse, CaseUpdate, MissingChildReportRequest, FoundChildReportRequest, HandoverRequest
)
from backend.app.services.bandham_service import BandhamService
from backend.app.services.conversation_engine import generate_telugu_pa_script
from backend.app.services.whatsapp_service import WhatsAppService
from backend.app.api.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/cases", tags=["Helpdesk & Operations"])


@router.get("", response_model=List[CaseResponse])
async def list_cases(
    case_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    """
    Lists child-safety cases with role-based restriction.
    Only authorized helpdesk & admin staff can access sensitive cases.
    """
    query = select(Case).order_by(Case.created_at.desc())
    if case_type:
        query = query.where(Case.case_type == case_type)
    if status_filter:
        query = query.where(Case.status == status_filter)
    if search:
        s = f"%{search}%"
        query = query.where(
            or_(
                Case.case_number.ilike(s),
                Case.band_id.ilike(s),
                Case.reported_by_name.ilike(s),
                Case.location_name.ilike(s)
            )
        )
    result = await db.execute(query)
    cases = result.scalars().all()

    responses = []
    for c in cases:
        notifs_res = await db.execute(
            select(NotificationAttempt).where(NotificationAttempt.case_id == c.id)
        )
        notifs = notifs_res.scalars().all()
        responses.append(CaseResponse(
            id=c.id,
            case_number=c.case_number,
            case_type=c.case_type,
            band_id=c.band_id,
            cluster_id=c.cluster_id,
            reported_by_name=c.reported_by_name,
            reporter_contact=c.reporter_contact,
            reporter_role=c.reporter_role,
            location_name=c.location_name,
            latitude=c.latitude,
            longitude=c.longitude,
            location_accuracy=c.location_accuracy,
            location_type=c.location_type,
            status=c.status,
            assigned_to_name=c.assigned_to_name,
            handover_method=c.handover_method,
            handover_notes=c.handover_notes,
            bolo_details_json=c.bolo_details_json,
            telugu_announcement_script=c.telugu_announcement_script,
            created_at=c.created_at,
            updated_at=c.updated_at,
            notification_attempts=notifs
        ))
    return responses


@router.post("/missing-child")
async def report_missing_child(
    req: MissingChildReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    """
    Staff-initiated Missing Child Case:
    - BOLO creation
    - Auto-generation of Telugu Public Address broadcast script
    - Immediate case dispatch to field runners
    """
    case_no = f"CASE-2027-{secrets.randbelow(9000) + 1000}"

    cluster_id = None
    if req.band_id:
        b_res = await db.execute(select(Band).where(Band.band_id == req.band_id.upper()))
        band_obj = b_res.scalar_one_or_none()
        if band_obj:
            cluster_id = band_obj.cluster_id

    # Find latest scan information (treated explicitly as LAST-KNOWN, not real-time!)
    latest_scan_note = None
    if req.band_id:
        scan_res = await db.execute(
            select(ScanLog).where(ScanLog.band_id == req.band_id.upper()).order_by(ScanLog.created_at.desc()).limit(1)
        )
        latest_scan = scan_res.scalar_one_or_none()
        if latest_scan:
            latest_scan_note = f"Last-known scan at {latest_scan.manual_location or 'GPS Fix'} on {latest_scan.created_at.strftime('%H:%M:%S')}"

    # Auto-generate Telugu PA script for ghat operator
    pa_script = generate_telugu_pa_script(
        child_name=req.child_name,
        age=req.child_age,
        clothing=req.clothing_description,
        last_seen=req.last_seen_location
    )

    bolo_payload = {
        "child_name": req.child_name,
        "age": req.child_age,
        "clothing": req.clothing_description,
        "last_seen": req.last_seen_location,
        "notes": req.notes,
        "last_known_scan_clue": latest_scan_note
    }

    new_case = Case(
        case_number=case_no,
        case_type="MISSING_CHILD",
        band_id=req.band_id.upper() if req.band_id else None,
        cluster_id=cluster_id,
        reported_by_name=f"Guardian ({req.child_name}'s family)",
        reporter_contact=req.guardian_phone,
        reporter_role="GUARDIAN",
        location_name=req.last_seen_location,
        status="OPEN",
        assigned_to_user_id=current_user.id,
        assigned_to_name=current_user.full_name,
        bolo_details_json=json.dumps(bolo_payload),
        telugu_announcement_script=pa_script
    )
    db.add(new_case)

    audit = AuditLog(
        action="MISSING_CHILD_CASE_OPENED",
        entity_type="CASE",
        entity_id=case_no,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name,
        details_json=json.dumps({"child_name": req.child_name, "last_seen": req.last_seen_location})
    )
    db.add(audit)
    await db.commit()

    return {
        "case_number": case_no,
        "status": "OPEN",
        "telugu_announcement_script": pa_script,
        "last_known_scan_clue": latest_scan_note
    }


@router.patch("/{case_id}")
async def update_case(
    case_id: int,
    data: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")

    old_status = c.status
    if data.status:
        c.status = data.status
    if data.assigned_to_name:
        c.assigned_to_name = data.assigned_to_name
    if data.assigned_to_user_id:
        c.assigned_to_user_id = data.assigned_to_user_id

    audit = AuditLog(
        action="CASE_UPDATED",
        entity_type="CASE",
        entity_id=c.case_number,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name,
        details_json=json.dumps({"old_status": old_status, "new_status": c.status, "notes": data.notes})
    )
    db.add(audit)
    await db.commit()

    return {"case_id": c.id, "case_number": c.case_number, "status": c.status}


@router.post("/{case_id}/verify-handover")
async def verify_and_handover_child(
    case_id: int,
    req: HandoverRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    """
    CRITICAL SAFEGUARDING STEP:
    Child handover is NEVER authorized by the band alone.
    Requires either:
    1. Successful Release PIN verification (delivered to registered guardian)
    2. Event-approved Safeguarding Fallback (e.g. parent lost phone, supervisor corroborates identity & contacts backup)
    """
    result = await db.execute(select(Case).where(Case.id == case_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")

    cluster = None
    if c.cluster_id:
        cl_res = await db.execute(select(FamilyCluster).where(FamilyCluster.id == c.cluster_id))
        cluster = cl_res.scalar_one_or_none()

    verification_method = req.fallback_method or "PIN_VERIFIED"

    if req.pin and cluster:
        # Validate PIN through Bandham Service
        is_valid, msg = await BandhamService.verify_release_pin(db, cluster, req.pin)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Handover authorization rejected: {msg}")
        verification_method = "PIN_VERIFIED"
    elif req.fallback_method:
        # Fallback procedure explicitly checked
        if req.fallback_method not in ["SUPERVISOR_APPROVED_FALLBACK", "POLICE_ESCALATION"]:
            raise HTTPException(status_code=400, detail="Invalid fallback verification procedure")
        verification_method = req.fallback_method
    else:
        raise HTTPException(status_code=400, detail="Either a valid Release PIN or supervisor fallback approval is required for child handover.")

    # Record safe handover and resolve case
    c.status = "RESOLVED"
    c.handover_method = verification_method
    c.handover_notes = f"Verified Guardian: {req.guardian_name_verified} ({req.guardian_phone_verified}). Notes: {req.notes}. Witness: {req.witness_staff_name}."
    c.witness_staff_id = current_user.id
    c.resolved_at = datetime.datetime.now(datetime.timezone.utc)

    # Log comprehensive immutable audit trail
    audit = AuditLog(
        action="CHILD_HANDOVER_VERIFIED_AND_RESOLVED",
        entity_type="CASE",
        entity_id=c.case_number,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name,
        details_json=json.dumps({
            "verification_method": verification_method,
            "guardian_name": req.guardian_name_verified,
            "guardian_phone": req.guardian_phone_verified[-4:],  # Masked in audit
            "witness": req.witness_staff_name,
            "notes": req.notes
        })
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "HANDOVER_AUTHORIZED_AND_COMPLETED",
        "case_number": c.case_number,
        "verification_method": verification_method,
        "resolved_at": c.resolved_at
    }
