from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserLogin(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "HELPDESK_STAFF"


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class MemberSchema(BaseModel):
    name: str
    age: Optional[int] = None
    relation: str = "Family Member"
    notes: Optional[str] = None


class ClusterCreate(BaseModel):
    primary_guardian_name: str
    primary_phone: str
    backup_phone: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    consent_given: bool = True
    members: List[MemberSchema] = []
    bands_count: int = 1
    notes: Optional[str] = None


class WhatsAppRegistrationRequest(BaseModel):
    phone_number: str
    primary_guardian_name: str
    backup_phone: Optional[str] = None
    members: List[MemberSchema] = []
    bands_count: int = 1


class BandResponse(BaseModel):
    id: int
    band_id: str
    cluster_id: int
    assigned_member_name: Optional[str] = None
    assigned_member_age: Optional[int] = None
    status: str
    issued_at: Optional[datetime.datetime] = None
    public_scan_url: Optional[str] = None

    class Config:
        from_attributes = True


class BandStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class FamilyClusterResponse(BaseModel):
    id: int
    cluster_code: str
    registration_ref: Optional[str] = None
    primary_guardian_name: str
    primary_phone: str
    backup_phone: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    status: str
    consent_given: bool
    members_count: int
    members: List[Dict[str, Any]] = []
    bands: List[BandResponse] = []
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class PinVerifyRequest(BaseModel):
    cluster_id: int
    pin: str


class PinResetRequest(BaseModel):
    cluster_id: int
    authorized_reason: str


class FoundChildReportRequest(BaseModel):
    band_id: str
    finder_name: Optional[str] = None
    finder_contact: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    location_type: str = "MANUAL"
    notes: Optional[str] = None


class MissingChildReportRequest(BaseModel):
    band_id: Optional[str] = None
    cluster_code: Optional[str] = None
    guardian_phone: str
    child_name: str
    child_age: Optional[int] = None
    clothing_description: str
    last_seen_location: str
    notes: Optional[str] = None


class CaseUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    notes: Optional[str] = None


class HandoverRequest(BaseModel):
    pin: Optional[str] = None
    fallback_method: Optional[str] = None  # PIN_VERIFIED, SUPERVISOR_APPROVED_FALLBACK, POLICE_ESCALATION
    witness_staff_name: str
    guardian_name_verified: str
    guardian_phone_verified: str
    notes: str


class NotificationAttemptResponse(BaseModel):
    id: int
    recipient_phone: str
    channel: str
    status: str
    message_content: Optional[str] = None
    initiated_at: datetime.datetime
    delivered_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class CaseResponse(BaseModel):
    id: int
    case_number: str
    case_type: str
    band_id: Optional[str] = None
    cluster_id: Optional[int] = None
    reported_by_name: Optional[str] = None
    reporter_contact: Optional[str] = None
    reporter_role: str
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy: Optional[float] = None
    location_type: str
    status: str
    assigned_to_name: Optional[str] = None
    handover_method: Optional[str] = None
    handover_notes: Optional[str] = None
    bolo_details_json: Optional[str] = None
    telugu_announcement_script: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    notification_attempts: List[NotificationAttemptResponse] = []

    class Config:
        from_attributes = True


class SanitationCreate(BaseModel):
    facility_id: str
    facility_name: str
    ghat_name: str
    issue_type: str
    priority: str = "NORMAL"
    description: Optional[str] = None
    reporter_phone: Optional[str] = None
    reported_via: str = "WHATSAPP"
    before_photo_url: Optional[str] = None


class SanitationUpdate(BaseModel):
    status: Optional[str] = None
    assigned_team: Optional[str] = None
    cleaner_notes: Optional[str] = None
    after_photo_url: Optional[str] = None
    supervisor_notes: Optional[str] = None
    is_reopened: Optional[bool] = False


class SanitationResponse(BaseModel):
    id: int
    ticket_number: str
    facility_id: str
    facility_name: str
    ghat_name: str
    issue_type: str
    priority: str
    status: str
    reported_via: str
    reporter_phone: Optional[str] = None
    description: Optional[str] = None
    before_photo_url: Optional[str] = None
    after_photo_url: Optional[str] = None
    cleaner_notes: Optional[str] = None
    assigned_team: Optional[str] = None
    supervisor_notes: Optional[str] = None
    reopen_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class RateCardResponse(BaseModel):
    id: int
    category: str
    service_name: str
    approved_rate: float
    unit: str
    effective_date: str
    verified_by_authority: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class ScamReportCreate(BaseModel):
    service_category: str
    service_provider_identifier: Optional[str] = None
    demanded_amount: float
    official_amount: float
    location: str
    details: Optional[str] = None
    reporter_phone: Optional[str] = None


class ScamReportResponse(BaseModel):
    id: int
    report_number: str
    service_category: str
    service_provider_identifier: Optional[str] = None
    demanded_amount: float
    official_amount: float
    location: str
    details: Optional[str] = None
    reporter_phone: Optional[str] = None
    status: str
    action_taken: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: str
    actor_name: str
    details_json: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class SimulatorMessageRequest(BaseModel):
    phone_number: str = "919876543210"
    message_text: str
    button_payload: Optional[str] = None


class SimulatorMessageResponse(BaseModel):
    replies: List[str]
    session_language: str
    current_state: str
