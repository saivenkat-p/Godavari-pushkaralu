from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.models import AuditLog, User
from backend.app.schemas.schemas import AuditLogResponse
from backend.app.api.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/audit", tags=["Audit & Governance"])


@router.get("/logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "HELPDESK_STAFF"]))
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)

    result = await db.execute(query)
    return result.scalars().all()
