import secrets
import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.models import SanitationTicket, User, AuditLog
from backend.app.schemas.schemas import SanitationCreate, SanitationUpdate, SanitationResponse
from backend.app.api.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/sanitation", tags=["Sanitation Dispatch"])


@router.get("/tickets", response_model=List[SanitationResponse])
async def list_sanitation_tickets(
    status_filter: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    ghat_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SANITATION_SUPERVISOR", "HELPDESK_STAFF"]))
):
    query = select(SanitationTicket).order_by(SanitationTicket.created_at.desc())
    if status_filter:
        query = query.where(SanitationTicket.status == status_filter)
    if priority:
        query = query.where(SanitationTicket.priority == priority)
    if ghat_name:
        query = query.where(SanitationTicket.ghat_name.ilike(f"%{ghat_name}%"))

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/tickets", response_model=SanitationResponse)
async def create_sanitation_ticket(
    req: SanitationCreate,
    db: AsyncSession = Depends(get_db)
):
    ticket_no = f"SAN-2027-{secrets.randbelow(9000) + 1000}"
    ticket = SanitationTicket(
        ticket_number=ticket_no,
        facility_id=req.facility_id,
        facility_name=req.facility_name,
        ghat_name=req.ghat_name,
        issue_type=req.issue_type,
        priority=req.priority,
        status="REPORTED",
        reported_via=req.reported_via,
        reporter_phone=req.reporter_phone,
        description=req.description,
        before_photo_url=req.before_photo_url
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.patch("/tickets/{ticket_id}", response_model=SanitationResponse)
async def update_sanitation_ticket(
    ticket_id: int,
    req: SanitationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "SANITATION_SUPERVISOR"]))
):
    """
    Supervisor updates ticket status:
    - Assign clean team
    - Upload after-cleaning photo evidence
    - Supervisor sign-off or reopen
    """
    result = await db.execute(select(SanitationTicket).where(SanitationTicket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Sanitation ticket not found")

    old_status = ticket.status
    if req.status:
        ticket.status = req.status
    if req.assigned_team:
        ticket.assigned_team = req.assigned_team
    if req.cleaner_notes:
        ticket.cleaner_notes = req.cleaner_notes
    if req.after_photo_url:
        ticket.after_photo_url = req.after_photo_url
    if req.supervisor_notes:
        ticket.supervisor_notes = req.supervisor_notes

    if req.is_reopened:
        ticket.reopen_count += 1
        ticket.status = "REOPENED"

    audit = AuditLog(
        action="SANITATION_TICKET_UPDATED",
        entity_type="SANITATION_TICKET",
        entity_id=ticket.ticket_number,
        actor_user_id=current_user.id,
        actor_name=current_user.full_name,
        details_json=json.dumps({"old_status": old_status, "new_status": ticket.status, "reopen_count": ticket.reopen_count})
    )
    db.add(audit)
    await db.commit()
    await db.refresh(ticket)
    return ticket
