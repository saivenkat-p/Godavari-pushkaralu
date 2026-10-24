export interface User {
  id: number;
  username: string;
  full_name: string;
  role: 'ADMIN' | 'HELPDESK_STAFF' | 'REGISTRATION_OPERATOR' | 'SANITATION_SUPERVISOR';
  is_active: boolean;
}

export interface Member {
  name: string;
  age?: number;
  relation?: string;
  notes?: string;
}

export interface Band {
  id: number;
  band_id: string;
  cluster_id: number;
  assigned_member_name?: string;
  assigned_member_age?: number;
  status: 'UNASSIGNED' | 'ISSUED' | 'ACTIVE' | 'LOST' | 'DAMAGED' | 'REVOKED' | 'REPLACED';
  issued_at?: string;
  public_scan_url?: string;
}

export interface FamilyCluster {
  id: number;
  cluster_code: string;
  registration_ref?: string;
  primary_guardian_name: string;
  primary_phone: string;
  backup_phone?: string;
  whatsapp_phone?: string;
  status: 'PENDING_VERIFICATION' | 'VERIFIED_ACTIVE' | 'CLOSED';
  consent_given: boolean;
  members_count: number;
  members: Member[];
  bands: Band[];
  created_at: string;
}

export interface NotificationAttempt {
  id: number;
  recipient_phone: string;
  channel: string;
  status: 'INITIATED' | 'ACCEPTED_BY_PROVIDER' | 'DELIVERED' | 'FAILED';
  message_content?: string;
  initiated_at: string;
  delivered_at?: string;
}

export interface Case {
  id: number;
  case_number: string;
  case_type: 'FOUND_CHILD' | 'MISSING_CHILD' | 'ELDERLY_SEPARATION';
  band_id?: string;
  cluster_id?: number;
  reported_by_name?: string;
  reporter_contact?: string;
  reporter_role: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  location_accuracy?: number;
  location_type: string;
  status: 'OPEN' | 'ASSIGNED' | 'RESPONDER_EN_ROUTE' | 'SAFEGUARDING_VERIFIED' | 'RESOLVED' | 'ESCALATED' | 'FALSE_REPORT';
  assigned_to_name?: string;
  handover_method?: string;
  handover_notes?: string;
  bolo_details_json?: string;
  telugu_announcement_script?: string;
  created_at: string;
  updated_at: string;
  notification_attempts: NotificationAttempt[];
}

export interface SanitationTicket {
  id: number;
  ticket_number: string;
  facility_id: string;
  facility_name: string;
  ghat_name: string;
  issue_type: string;
  priority: 'URGENT' | 'HIGH' | 'NORMAL';
  status: 'REPORTED' | 'ASSIGNED' | 'IN_PROGRESS' | 'CLEANED_PENDING_INSPECTION' | 'RESOLVED_VERIFIED' | 'REOPENED';
  reported_via: string;
  reporter_phone?: string;
  description?: string;
  before_photo_url?: string;
  after_photo_url?: string;
  cleaner_notes?: string;
  assigned_team?: string;
  supervisor_notes?: string;
  reopen_count: number;
  created_at: string;
  updated_at: string;
}

export interface RateCard {
  id: number;
  category: string;
  service_name: string;
  approved_rate: number;
  unit: string;
  effective_date: string;
  verified_by_authority: string;
  notes?: string;
}

export interface ScamReport {
  id: number;
  report_number: string;
  service_category: string;
  service_provider_identifier?: string;
  demanded_amount: number;
  official_amount: number;
  location: string;
  details?: string;
  reporter_phone?: string;
  status: 'SUBMITTED' | 'UNDER_REVIEW' | 'ENFORCEMENT_NOTIFIED' | 'RESOLVED';
  action_taken?: string;
  created_at: string;
}

export interface AuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string;
  actor_name: string;
  details_json?: string;
  ip_address?: string;
  created_at: string;
}
