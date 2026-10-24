import hashlib
import json
import secrets
import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.models.models import Band, FamilyCluster, Case, ScanLog, NotificationAttempt, AuditLog
from backend.app.schemas.schemas import FoundChildReportRequest
from backend.app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/api/scan", tags=["Public QR Scan"])


@router.get("/{band_id}")
async def get_public_scan_info(
    band_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Public anonymous QR scan view:
    - Provides safe instructions and reporting options.
    - NEVER exposes child's name, parent's name, or phone numbers.
    - Records scan timestamp & anonymized IP hash.
    """
    result = await db.execute(select(Band).where(Band.band_id == band_id.upper()))
    band = result.scalar_one_or_none()
    if not band:
        raise HTTPException(status_code=404, detail="Bandham QR code not recognized in the festival grid.")

    # Record scan log
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()
    user_agent = request.headers.get("user-agent", "")[:190]

    scan_entry = ScanLog(
        band_id=band.band_id,
        ip_hash=ip_hash,
        user_agent=user_agent
    )
    db.add(scan_entry)
    await db.commit()

    return {
        "band_id": band.band_id,
        "is_active": band.status == "ACTIVE" or band.status == "ISSUED",
        "emergency_helpline": "1800-425-2027",
        "police_control": "112",
        "safe_instructions": [
            "Please stay calm and keep the child safe and in sight.",
            "NEVER hand the child to an unverified stranger or crowd member.",
            "Bring the child to the nearest designated Helpdesk or uniformed Police officer.",
            "Tap 'Report Found Child' below to immediately alert the family and operations grid."
        ],
        "nearest_helpdesks": [
            {"name": "Kotilingala Helpdesk Booth #1", "location": "Kotilingala Ghat Center (Pillar 14)"},
            {"name": "Pushkar Ghat Lost Child Center", "location": "Main Entrance, Station Road"},
            {"name": "Goshpada Kshetram Helpdesk", "location": "Kovvur Main Bus Bay"}
        ]
    }


@router.post("/{band_id}/report-found")
async def report_found_child_from_scan(
    band_id: str,
    req: FoundChildReportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Finder submits found-child report from the mobile QR scan page.
    Creates a real Case record and triggers a notification attempt to the verified guardian.
    """
    result = await db.execute(select(Band).where(Band.band_id == band_id.upper()))
    band = result.scalar_one_or_none()
    if not band:
        raise HTTPException(status_code=404, detail="Bandham QR code not recognized")

    cluster = None
    if band.cluster_id:
        c_res = await db.execute(select(FamilyCluster).where(FamilyCluster.id == band.cluster_id))
        cluster = c_res.scalar_one_or_none()

    case_no = f"CASE-2027-{secrets.randbelow(9000) + 1000}"
    location_desc = req.location_name or f"GPS: {req.latitude}, {req.longitude}" if req.latitude else "Ghat Pushkaralu Zone"

    new_case = Case(
        case_number=case_no,
        case_type="FOUND_CHILD",
        band_id=band.band_id,
        cluster_id=band.cluster_id,
        reported_by_name=req.finder_name or "Helpful Citizen Scanner",
        reporter_contact=req.finder_contact,
        reporter_role="FINDER",
        location_name=location_desc,
        latitude=req.latitude,
        longitude=req.longitude,
        location_accuracy=req.accuracy,
        location_type=req.location_type,
        status="OPEN"
    )
    db.add(new_case)
    await db.flush()

    # Trigger dual notification attempt to guardian
    notif_id = None
    if cluster and cluster.primary_phone:
        guardian_msg = (
            f"🚨 *BANDHAM CHILD SAFETY ALERT!*\n\n"
            f"A pilgrim has scanned wristband *{band.band_id}* and reported your family member safe at:\n"
            f"📍 *{location_desc}*\n\n"
            f"Please proceed immediately to the nearest Helpdesk or Police post. "
            f"Case Reference: *{case_no}*. Do not share your Release PIN with anyone except verified desk staff."
        )

        notif = NotificationAttempt(
            case_id=new_case.id,
            cluster_id=cluster.id,
            recipient_phone=cluster.primary_phone,
            channel="WHATSAPP",
            status="INITIATED",
            message_content=guardian_msg
        )
        db.add(notif)
        await db.flush()
        notif_id = notif.id

        # Dispatch via WhatsApp Service
        dispatch_result = await WhatsAppService.send_text_message(
            to_phone=cluster.primary_phone,
            message_text=guardian_msg
        )
        if dispatch_result.get("status") in ["DELIVERED_TO_PROVIDER", "SIMULATED_SUCCESS"]:
            notif.status = "ACCEPTED_BY_PROVIDER"
            notif.delivered_at = datetime.datetime.now(datetime.timezone.utc)
        else:
            notif.status = "FAILED"
            notif.error_details = str(dispatch_result.get("error"))

    # Log audit
    audit = AuditLog(
        action="FOUND_CHILD_REPORTED_FROM_SCAN",
        entity_type="CASE",
        entity_id=case_no,
        actor_name="PUBLIC_QR_SCANNER",
        details_json=json.dumps({"band_id": band.band_id, "location": location_desc})
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "REPORT_RECEIVED",
        "case_number": case_no,
        "guardian_alerted": bool(cluster and cluster.primary_phone),
        "instructions": "Thank you! Please stay with the child and proceed toward the nearest Pushkaralu Helpdesk or Police booth."
    }
