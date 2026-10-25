import io
import base64
import qrcode
import secrets
import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from backend.app.core.config import settings
from backend.app.models.models import FamilyCluster, Band, AuditLog

pin_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_secure_band_id() -> str:
    """
    Generates a cryptographically random, non-guessable 8-character hex band ID.
    Format: BND-A9F23D81
    """
    return f"BND-{secrets.token_hex(4).upper()}"


def generate_release_pin() -> str:
    """
    Generates a 6-digit release PIN for safe handover verification.
    """
    return f"{secrets.randbelow(900000) + 100000}"


def generate_qr_data_url(band_id: str) -> str:
    """
    Generates a high-contrast QR code image as a base64 data URI.
    The public QR payload ONLY contains the public URL with the random band ID,
    NEVER personal names, phone numbers, or guardian details!
    """
    public_url = f"{settings.PUBLIC_BASE_URL}/scan/{band_id}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for festival conditions
        box_size=10,
        border=2,
    )
    qr.add_data(public_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


class BandhamService:

    @classmethod
    async def create_family_cluster(
        cls,
        db: AsyncSession,
        primary_guardian_name: str,
        primary_phone: str,
        backup_phone: Optional[str] = None,
        whatsapp_phone: Optional[str] = None,
        members: Optional[List[Dict[str, Any]]] = None,
        bands_count: int = 1,
        notes: Optional[str] = None,
        actor_name: str = "STAFF",
        actor_user_id: Optional[int] = None
    ) -> Tuple[FamilyCluster, List[Band], str]:
        """
        Creates a family cluster, generates requested wristbands with cryptographic IDs,
        and creates an expiring 6-digit Release PIN.
        """
        cluster_code = f"FAM-{secrets.token_hex(3).upper()}"
        plain_pin = generate_release_pin()
        pin_hash = pin_context.hash(plain_pin)
        pin_expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12)

        import json
        cluster = FamilyCluster(
            cluster_code=cluster_code,
            primary_guardian_name=primary_guardian_name,
            primary_phone=primary_phone,
            backup_phone=backup_phone,
            whatsapp_phone=whatsapp_phone or primary_phone,
            consent_given=True,
            status="VERIFIED_ACTIVE",
            members_count=bands_count,
            members_json=json.dumps(members or []),
            notes=notes,
            release_pin_hash=pin_hash,
            pin_failed_attempts=0,
            pin_expires_at=pin_expires
        )
        db.add(cluster)
        await db.flush()  # to obtain cluster.id

        issued_bands: List[Band] = []
        for i in range(bands_count):
            member_name = members[i].get("name") if members and i < len(members) else f"Member {i+1}"
            member_age = members[i].get("age") if members and i < len(members) else None
            band = Band(
                band_id=generate_secure_band_id(),
                cluster_id=cluster.id,
                assigned_member_name=member_name,
                assigned_member_age=member_age,
                status="ISSUED",
                issued_by_user_id=actor_user_id,
                issued_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(band)
            issued_bands.append(band)

        # Audit log
        audit = AuditLog(
            action="CLUSTER_AND_BANDS_CREATED",
            entity_type="FAMILY_CLUSTER",
            entity_id=cluster.cluster_code,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            details_json=json.dumps({
                "bands_count": bands_count,
                "primary_phone": primary_phone[-4:] if primary_phone else ""  # Masked for audit
            })
        )
        db.add(audit)
        await db.commit()
        await db.refresh(cluster)

        return cluster, issued_bands, plain_pin

    @classmethod
    async def verify_release_pin(cls, db: AsyncSession, cluster: FamilyCluster, pin_attempt: str) -> Tuple[bool, str]:
        """
        Safely verifies the 6-digit release PIN with brute-force attempt lockout.
        """
        if not cluster.release_pin_hash:
            return False, "No PIN set on this cluster."

        now = datetime.datetime.now(datetime.timezone.utc)
        if cluster.pin_expires_at and cluster.pin_expires_at.replace(tzinfo=datetime.timezone.utc) < now:
            return False, "PIN has expired. Supervisor identity verification required."

        if cluster.pin_failed_attempts >= 5:
            return False, "Maximum PIN attempts exceeded. Handover locked; must escalate to Police/Supervisor."

        if pin_context.verify(pin_attempt, cluster.release_pin_hash):
            cluster.pin_failed_attempts = 0
            await db.commit()
            return True, "PIN verified successfully."
        else:
            cluster.pin_failed_attempts += 1
            await db.commit()
            remaining = 5 - cluster.pin_failed_attempts
            return False, f"Invalid PIN. {remaining} attempt(s) remaining."

    @classmethod
    async def reset_release_pin(
        cls,
        db: AsyncSession,
        cluster: FamilyCluster,
        actor_name: str,
        actor_user_id: Optional[int],
        reason: str
    ) -> str:
        """
        Supervisor-authorized reset of Release PIN.
        """
        import json
        new_pin = generate_release_pin()
        cluster.release_pin_hash = pin_context.hash(new_pin)
        cluster.pin_failed_attempts = 0
        cluster.pin_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12)

        audit = AuditLog(
            action="PIN_RESET_AUTHORIZED",
            entity_type="FAMILY_CLUSTER",
            entity_id=cluster.cluster_code,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            details_json=json.dumps({"reason": reason})
        )
        db.add(audit)
        await db.commit()
        return new_pin
