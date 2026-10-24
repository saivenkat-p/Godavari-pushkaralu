import datetime
import secrets
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False, default="HELPDESK_STAFF")  # ADMIN, HELPDESK_STAFF, REGISTRATION_OPERATOR, SANITATION_SUPERVISOR
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class FamilyCluster(Base):
    __tablename__ = "family_clusters"

    id = Column(Integer, primary_key=True, index=True)
    cluster_code = Column(String(30), unique=True, index=True, nullable=False)
    registration_ref = Column(String(30), unique=True, index=True, nullable=True)  # WhatsApp pending reference (e.g., REG-824192)
    primary_guardian_name = Column(String(100), nullable=False)
    primary_phone = Column(String(20), index=True, nullable=False)
    backup_phone = Column(String(20), nullable=True)
    whatsapp_phone = Column(String(20), index=True, nullable=True)
    
    consent_given = Column(Boolean, default=True)
    consent_timestamp = Column(DateTime, default=utcnow)
    notes = Column(Text, nullable=True)
    
    members_count = Column(Integer, default=1)
    members_json = Column(Text, default="[]")  # List of member dicts: [{"name": "...", "age": 8, "relation": "Child"}]
    
    status = Column(String(30), default="PENDING_VERIFICATION")  # PENDING_VERIFICATION, VERIFIED_ACTIVE, CLOSED
    
    # Release PIN Lifecycle
    release_pin_hash = Column(String(200), nullable=True)
    pin_failed_attempts = Column(Integer, default=0)
    pin_expires_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    bands = relationship("Band", back_populates="cluster", cascade="all, delete-orphan")
    cases = relationship("Case", back_populates="cluster")


class Band(Base):
    __tablename__ = "bands"

    id = Column(Integer, primary_key=True, index=True)
    # Cryptographically random, non-guessable identifier (NEVER reveals child/parent info)
    band_id = Column(String(40), unique=True, index=True, nullable=False)
    cluster_id = Column(Integer, ForeignKey("family_clusters.id"), nullable=False)
    
    assigned_member_name = Column(String(100), nullable=True)
    assigned_member_age = Column(Integer, nullable=True)
    notes = Column(String(200), nullable=True)
    
    status = Column(String(30), default="ISSUED")  # UNASSIGNED, ISSUED, ACTIVE, LOST, DAMAGED, REVOKED, REPLACED
    issued_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    issued_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)

    cluster = relationship("FamilyCluster", back_populates="bands")
    cases = relationship("Case", back_populates="band")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(40), unique=True, index=True, nullable=False)
    case_type = Column(String(30), nullable=False)  # FOUND_CHILD, MISSING_CHILD, ELDERLY_SEPARATION
    
    band_id = Column(String(40), ForeignKey("bands.band_id"), nullable=True)
    cluster_id = Column(Integer, ForeignKey("family_clusters.id"), nullable=True)
    
    reported_by_name = Column(String(100), nullable=True)
    reporter_contact = Column(String(50), nullable=True)
    reporter_role = Column(String(30), default="FINDER")  # FINDER, GUARDIAN, STAFF
    
    location_name = Column(String(150), nullable=True)  # e.g., 'Kotilingala Ghat - Pillar 14'
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy = Column(Float, nullable=True)
    location_type = Column(String(20), default="MANUAL")  # GPS, MANUAL, HELPDESK_STALL
    
    status = Column(String(40), default="OPEN")  # OPEN, ASSIGNED, RESPONDER_EN_ROUTE, SAFEGUARDING_VERIFIED, RESOLVED, ESCALATED, FALSE_REPORT
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_to_name = Column(String(100), nullable=True)
    
    # Handover and Safeguarding Verification
    handover_method = Column(String(40), nullable=True)  # PIN_VERIFIED, SUPERVISOR_APPROVED_FALLBACK, POLICE_ESCALATION
    handover_notes = Column(Text, nullable=True)
    witness_staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # BOLO (Be On Look Out) & Public Address Broadcast Support
    bolo_details_json = Column(Text, nullable=True)  # clothing, age, description
    telugu_announcement_script = Column(Text, nullable=True)  # Script for PA operator
    
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    band = relationship("Band", back_populates="cases")
    cluster = relationship("FamilyCluster", back_populates="cases")
    notification_attempts = relationship("NotificationAttempt", back_populates="case", cascade="all, delete-orphan")


class NotificationAttempt(Base):
    __tablename__ = "notification_attempts"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)
    cluster_id = Column(Integer, ForeignKey("family_clusters.id"), nullable=True)
    
    recipient_phone = Column(String(30), nullable=False)
    channel = Column(String(20), default="WHATSAPP")  # WHATSAPP, SMS, VOICE_IVR
    
    # Delivery tracking: separate alert initiation from actual delivery
    status = Column(String(30), default="INITIATED")  # INITIATED, ACCEPTED_BY_PROVIDER, DELIVERED, FAILED
    message_content = Column(Text, nullable=True)
    provider_message_id = Column(String(100), nullable=True)
    error_details = Column(Text, nullable=True)
    
    initiated_at = Column(DateTime, default=utcnow)
    delivered_at = Column(DateTime, nullable=True)

    case = relationship("Case", back_populates="notification_attempts")


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    band_id = Column(String(40), index=True, nullable=False)
    ip_hash = Column(String(64), nullable=True)  # Anonymized IP hash
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    manual_location = Column(String(150), nullable=True)
    user_agent = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class SanitationTicket(Base):
    __tablename__ = "sanitation_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(40), unique=True, index=True, nullable=False)
    facility_id = Column(String(50), index=True, nullable=False)
    facility_name = Column(String(100), nullable=False)
    ghat_name = Column(String(100), nullable=False)
    
    issue_type = Column(String(50), nullable=False)  # OVERFLOW, NO_WATER, UNHYGIENIC, DAMAGED_FIXTURE
    priority = Column(String(20), default="NORMAL")  # URGENT, HIGH, NORMAL
    status = Column(String(40), default="REPORTED")  # REPORTED, ASSIGNED, IN_PROGRESS, CLEANED_PENDING_INSPECTION, RESOLVED_VERIFIED, REOPENED
    
    reported_via = Column(String(20), default="WHATSAPP")  # WHATSAPP, QR_SCAN, STAFF_PORTAL
    reporter_phone = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    
    before_photo_url = Column(String(255), nullable=True)
    after_photo_url = Column(String(255), nullable=True)
    cleaner_notes = Column(Text, nullable=True)
    assigned_team = Column(String(100), nullable=True)
    supervisor_notes = Column(Text, nullable=True)
    
    reopen_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class RateCard(Base):
    __tablename__ = "rate_cards"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), index=True, nullable=False)  # BOAT_RIDE, AUTO_RICKSHAW, TAXI, CLOAKROOM, TEMPLE_PRASADAM
    service_name = Column(String(100), nullable=False)
    approved_rate = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)  # per person, per km, per item/hour
    effective_date = Column(String(50), default="October 2026 - July 2027")
    verified_by_authority = Column(String(150), default="East Godavari District Collectorate & Tourism Dept")
    notes = Column(Text, nullable=True)


class ScamReport(Base):
    __tablename__ = "scam_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_number = Column(String(40), unique=True, index=True, nullable=False)
    service_category = Column(String(50), nullable=False)
    service_provider_identifier = Column(String(100), nullable=True)  # Vehicle number, stall #, boat ID
    demanded_amount = Column(Float, nullable=False)
    official_amount = Column(Float, nullable=False)
    location = Column(String(150), nullable=False)
    details = Column(Text, nullable=True)
    reporter_phone = Column(String(30), nullable=True)
    
    status = Column(String(40), default="SUBMITTED")  # SUBMITTED, UNDER_REVIEW, ENFORCEMENT_NOTIFIED, RESOLVED
    action_taken = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(80), nullable=False)  # e.g., BAND_ISSUED, PIN_VERIFIED, CASE_STATUS_UPDATE, REPRINT_LABEL
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=False)
    actor_user_id = Column(Integer, nullable=True)
    actor_name = Column(String(100), nullable=False, default="SYSTEM")
    details_json = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(30), unique=True, index=True, nullable=False)
    language = Column(String(10), default="te")  # 'te' (Telugu), 'en' (English), 'hi' (Hindi)
    current_state = Column(String(50), default="MAIN_MENU")
    context_data_json = Column(Text, default="{}")
    last_interaction_at = Column(DateTime, default=utcnow)
