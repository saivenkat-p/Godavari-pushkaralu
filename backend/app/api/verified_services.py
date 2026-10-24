import secrets
import json
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.models import RateCard, ScamReport, User, AuditLog
from backend.app.schemas.schemas import RateCardResponse, ScamReportCreate, ScamReportResponse
from backend.app.api.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/services", tags=["Verified Services & Scam Reports"])


@router.get("/rate-cards", response_model=List[RateCardResponse])
async def list_rate_cards(
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Public and staff accessible official verified rate cards.
    """
    query = select(RateCard)
    if category:
        query = query.where(RateCard.category == category)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/scam-reports", response_model=List[ScamReportResponse])
async def list_scam_reports(
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    query = select(ScamReport).order_by(ScamReport.created_at.desc())
    if status_filter:
        query = query.where(ScamReport.status == status_filter)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/scam-reports", response_model=ScamReportResponse)
async def create_scam_report(
    req: ScamReportCreate,
    db: AsyncSession = Depends(get_db)
):
    report_no = f"SCAM-2027-{secrets.randbelow(9000) + 1000}"
    scam = ScamReport(
        report_number=report_no,
        service_category=req.service_category,
        service_provider_identifier=req.service_provider_identifier,
        demanded_amount=req.demanded_amount,
        official_amount=req.official_amount,
        location=req.location,
        details=req.details,
        reporter_phone=req.reporter_phone,
        status="SUBMITTED"
    )
    db.add(scam)
    await db.commit()
    await db.refresh(scam)
    return scam


@router.patch("/scam-reports/{report_id}", response_model=ScamReportResponse)
async def update_scam_report(
    report_id: int,
    status: str,
    action_taken: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    result = await db.execute(select(ScamReport).where(ScamReport.id == report_id))
    scam = result.scalar_one_or_none()
    if not scam:
        raise HTTPException(status_code=404, detail="Scam report not found")

    scam.status = status
    scam.action_taken = action_taken

    audit = AuditLog(
        action="SCAM_REPORT_ENFORCEMENT_ACTION",
        entity_type="SCAM_REPORT",
        entity_id=scam.report_number,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name,
        details_json=json.dumps({"status": status, "action": action_taken})
    )
    db.add(audit)
    await db.commit()
    await db.refresh(scam)
    return scam
