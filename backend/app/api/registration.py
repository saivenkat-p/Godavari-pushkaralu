import json
import secrets
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.models import FamilyCluster, Band, User, AuditLog
from backend.app.schemas.schemas import (
    ClusterCreate, FamilyClusterResponse, BandResponse, BandStatusUpdate, PinResetRequest
)
from backend.app.services.bandham_service import BandhamService, generate_qr_data_url, generate_secure_band_id
from backend.app.api.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/registration", tags=["Registration & Band Issuance"])


@router.post("/cluster")
async def create_cluster(
    data: ClusterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "REGISTRATION_OPERATOR"]))
):
    """
    Assisted stall registration:
    Operator links wristbands to a family cluster, records guardian and member details,
    generates secure Band IDs, and issues a private Release PIN.
    """
    cluster, bands, plain_pin = await BandhamService.create_family_cluster(
        db=db,
        primary_guardian_name=data.primary_guardian_name,
        primary_phone=data.primary_phone,
        backup_phone=data.backup_phone,
        whatsapp_phone=data.whatsapp_phone,
        members=[m.model_dump() for m in data.members],
        bands_count=data.bands_count,
        notes=data.notes,
        actor_name=current_user.full_name,
        actor_user_id=current_user.id
    )

    return {
        "status": "SUCCESS",
        "cluster_code": cluster.cluster_code,
        "cluster_id": cluster.id,
        "primary_guardian_name": cluster.primary_guardian_name,
        "release_pin": plain_pin,  # Handed over once in person to the guardian
        "bands": [
            {
                "id": b.id,
                "band_id": b.band_id,
                "assigned_member_name": b.assigned_member_name,
                "status": b.status,
                "qr_image_data": generate_qr_data_url(b.band_id)
            }
            for b in bands
        ]
    }


@router.get("/pending", response_model=List[FamilyClusterResponse])
async def list_pending_registrations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "REGISTRATION_OPERATOR", "HELPDESK_STAFF"]))
):
    """
    Lists pending pre-registrations submitted by pilgrims through WhatsApp.
    Stall operators can search and claim these when the family arrives at the counter.
    """
    result = await db.execute(
        select(FamilyCluster)
        .where(FamilyCluster.status == "PENDING_VERIFICATION")
        .order_by(FamilyCluster.created_at.desc())
    )
    clusters = result.scalars().all()
    
    responses = []
    for c in clusters:
        members_list = json.loads(c.members_json) if c.members_json else []
        responses.append(FamilyClusterResponse(
            id=c.id,
            cluster_code=c.cluster_code,
            registration_ref=c.registration_ref,
            primary_guardian_name=c.primary_guardian_name,
            primary_phone=c.primary_phone,
            backup_phone=c.backup_phone,
            whatsapp_phone=c.whatsapp_phone,
            status=c.status,
            consent_given=c.consent_given,
            members_count=c.members_count,
            members=members_list,
            bands=[],
            created_at=c.created_at
        ))
    return responses


@router.post("/claim-pending/{ref}")
async def claim_and_issue_pending(
    ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "REGISTRATION_OPERATOR"]))
):
    """
    Completes in-person verification for a pending WhatsApp registration:
    Activates the cluster, creates the required physical wristbands,
    and returns printable labels with the secret Release PIN.
    """
    result = await db.execute(
        select(FamilyCluster).where(
            or_(FamilyCluster.registration_ref == ref.upper(), FamilyCluster.cluster_code == ref.upper())
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Pending registration reference not found")

    if cluster.status == "VERIFIED_ACTIVE":
        raise HTTPException(status_code=400, detail="This registration has already been verified and issued")

    # Generate Release PIN and issue wristbands
    from backend.app.services.bandham_service import generate_release_pin, pin_context
    plain_pin = generate_release_pin()
    cluster.release_pin_hash = pin_context.hash(plain_pin)
    cluster.pin_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12)
    cluster.pin_failed_attempts = 0
    cluster.status = "VERIFIED_ACTIVE"

    issued_bands = []
    for i in range(cluster.members_count):
        band = Band(
            band_id=generate_secure_band_id(),
            cluster_id=cluster.id,
            assigned_member_name=f"Family Member {i+1}",
            status="ISSUED",
            issued_by_user_id=current_user.id,
            issued_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(band)
        issued_bands.append(band)

    # Audit
    audit = AuditLog(
        action="PENDING_REGISTRATION_CLAIMED_AND_ISSUED",
        entity_type="FAMILY_CLUSTER",
        entity_id=cluster.cluster_code,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name,
        details_json=json.dumps({"ref": ref, "bands_count": cluster.members_count})
    )
    db.add(audit)
    await db.commit()

    return {
        "status": "ISSUED",
        "cluster_code": cluster.cluster_code,
        "registration_ref": cluster.registration_ref,
        "primary_guardian_name": cluster.primary_guardian_name,
        "release_pin": plain_pin,
        "bands": [
            {
                "id": b.id,
                "band_id": b.band_id,
                "assigned_member_name": b.assigned_member_name,
                "status": b.status,
                "qr_image_data": generate_qr_data_url(b.band_id)
            }
            for b in issued_bands
        ]
    }


@router.get("/clusters", response_model=List[FamilyClusterResponse])
async def list_clusters(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "REGISTRATION_OPERATOR", "HELPDESK_STAFF"]))
):
    query = select(FamilyCluster).order_by(FamilyCluster.created_at.desc())
    if status_filter:
        query = query.where(FamilyCluster.status == status_filter)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                FamilyCluster.primary_guardian_name.ilike(search_term),
                FamilyCluster.primary_phone.ilike(search_term),
                FamilyCluster.cluster_code.ilike(search_term),
                FamilyCluster.registration_ref.ilike(search_term)
            )
        )
    result = await db.execute(query)
    clusters = result.scalars().all()

    responses = []
    for c in clusters:
        # Load bands
        bands_res = await db.execute(select(Band).where(Band.cluster_id == c.id))
        bands = bands_res.scalars().all()

        bands_data = [
            BandResponse(
                id=b.id,
                band_id=b.band_id,
                cluster_id=b.cluster_id,
                assigned_member_name=b.assigned_member_name,
                assigned_member_age=b.assigned_member_age,
                status=b.status,
                issued_at=b.issued_at,
                public_scan_url=f"/scan/{b.band_id}"
            )
            for b in bands
        ]

        members_list = json.loads(c.members_json) if c.members_json else []
        responses.append(FamilyClusterResponse(
            id=c.id,
            cluster_code=c.cluster_code,
            registration_ref=c.registration_ref,
            primary_guardian_name=c.primary_guardian_name,
            primary_phone=c.primary_phone,
            backup_phone=c.backup_phone,
            whatsapp_phone=c.whatsapp_phone,
            status=c.status,
            consent_given=c.consent_given,
            members_count=c.members_count,
            members=members_list,
            bands=bands_data,
            created_at=c.created_at
        ))
    return responses


@router.get("/bands/{band_id}/label")
async def get_band_label(
    band_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "REGISTRATION_OPERATOR", "HELPDESK_STAFF"]))
):
    """
    Returns printable label layout data:
    - QR Code data URI
    - Band ID
    - Helpline Number
    - SAFEGUARD: NEVER contains names or phone numbers!
    """
    result = await db.execute(select(Band).where(Band.band_id == band_id))
    band = result.scalar_one_or_none()
    if not band:
        raise HTTPException(status_code=404, detail="Band not found")

    qr_image = generate_qr_data_url(band.band_id)

    # Log reprint audit
    audit = AuditLog(
        action="BAND_LABEL_PRINT_REQUESTED",
        entity_type="BAND",
        entity_id=band.band_id,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name
    )
    db.add(audit)
    await db.commit()

    return {
        "band_id": band.band_id,
        "qr_image_data": qr_image,
        "festival": "Godavari Pushkaralu 2027",
        "emergency_helpline": "1800-425-2027",
        "police_control": "112",
        "instructions": "If found, scan QR or visit any Pushkaralu Helpdesk.",
        "status": band.status
    }


@router.patch("/bands/{band_id}/status")
async def update_band_status(
    band_id: str,
    update: BandStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "REGISTRATION_OPERATOR", "HELPDESK_STAFF"]))
):
    valid_statuses = ["ISSUED", "ACTIVE", "LOST", "DAMAGED", "REVOKED", "REPLACED"]
    if update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {valid_statuses}")

    result = await db.execute(select(Band).where(Band.band_id == band_id))
    band = result.scalar_one_or_none()
    if not band:
        raise HTTPException(status_code=404, detail="Band not found")

    old_status = band.status
    band.status = update.status

    audit = AuditLog(
        action="BAND_STATUS_CHANGED",
        entity_type="BAND",
        entity_id=band.band_id,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name,
        details_json=json.dumps({"old_status": old_status, "new_status": update.status, "notes": update.notes})
    )
    db.add(audit)
    await db.commit()

    return {"band_id": band_id, "status": band.status, "updated_by": current_user.full_name}


@router.post("/clusters/{cluster_id}/reset-pin")
async def reset_cluster_pin(
    cluster_id: int,
    req: PinResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    result = await db.execute(select(FamilyCluster).where(FamilyCluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    new_pin = await BandhamService.reset_release_pin(
        db=db,
        cluster=cluster,
        actor_name=current_user.full_name,
        actor_user_id=current_user.id,
        reason=req.authorized_reason
    )

    return {
        "status": "PIN_RESET_SUCCESSFUL",
        "cluster_code": cluster.cluster_code,
        "new_release_pin": new_pin
    }
