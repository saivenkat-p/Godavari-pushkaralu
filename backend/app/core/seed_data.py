import json
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.security import get_password_hash
from backend.app.models.models import (
    User, FamilyCluster, Band, Case, NotificationAttempt, SanitationTicket, RateCard, ScamReport, ScanLog, AuditLog
)
from backend.app.services.bandham_service import BandhamService, pin_context


async def seed_database(db: AsyncSession):
    # Check if already seeded
    existing_user = await db.execute(select(User).limit(1))
    if existing_user.scalar_one_or_none():
        return

    # 1. Create Default Staff Users
    users = [
        User(
            username="admin",
            hashed_password=get_password_hash(settings.SEED_ADMIN_PASSWORD),
            full_name="District Administrator (Pushkaralu Command)",
            role="ADMIN"
        ),
        User(
            username="helpdesk_operator",
            hashed_password=get_password_hash(settings.SEED_HELPDESK_PASSWORD),
            full_name="K. Lakshmi (Kotilingala Ghat Helpdesk)",
            role="HELPDESK_STAFF"
        ),
        User(
            username="reg_operator",
            hashed_password=get_password_hash(settings.SEED_REG_PASSWORD),
            full_name="P. Ramesh (Stall #1 Registration Lead)",
            role="REGISTRATION_OPERATOR"
        ),
        User(
            username="sanitation_lead",
            hashed_password=get_password_hash(settings.SEED_SANITATION_PASSWORD),
            full_name="M. Srinivas (Zonal Sanitation Inspector)",
            role="SANITATION_SUPERVISOR"
        )
    ]
    for u in users:
        db.add(u)
    await db.flush()

    # 2. Sample Pending WhatsApp Registration (waiting for stall verification)
    pending_cluster = FamilyCluster(
        cluster_code="FAM-PENDING01",
        registration_ref="REG-782104",
        primary_guardian_name="Venkateswara Rao",
        primary_phone="919876543210",
        backup_phone="919876543219",
        whatsapp_phone="919876543210",
        consent_given=True,
        status="PENDING_VERIFICATION",
        members_count=3,
        members_json=json.dumps([
            {"name": "Sai Krishna (Child)", "age": 7, "relation": "Child"},
            {"name": "Ananya (Child)", "age": 5, "relation": "Child"},
            {"name": "Lakshmi (Mother)", "age": 34, "relation": "Spouse"}
        ]),
        notes="Pre-registered via WhatsApp Assistant. Awaiting physical wristband issuance at Kotilingala Stall."
    )
    db.add(pending_cluster)

    # 3. Sample Active Family Cluster with Issued Wristbands
    pin_hash = pin_context.hash("482915")
    active_cluster = FamilyCluster(
        cluster_code="FAM-82A1B",
        registration_ref="REG-551092",
        primary_guardian_name="Subba Rao",
        primary_phone="919848022338",
        backup_phone="919440188221",
        whatsapp_phone="919848022338",
        consent_given=True,
        status="VERIFIED_ACTIVE",
        members_count=2,
        members_json=json.dumps([
            {"name": "Chaitanya", "age": 8, "relation": "Son"},
            {"name": "Bhavani", "age": 68, "relation": "Grandmother"}
        ]),
        release_pin_hash=pin_hash,
        pin_failed_attempts=0,
        pin_expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12),
        notes="Verified in-person at Pushkar Ghat Stall."
    )
    db.add(active_cluster)
    await db.flush()

    band1 = Band(
        band_id="BND-8F32A1C9",
        cluster_id=active_cluster.id,
        assigned_member_name="Chaitanya",
        assigned_member_age=8,
        status="ACTIVE",
        issued_by_user_id=users[2].id,
        issued_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
    )
    band2 = Band(
        band_id="BND-4B90E712",
        cluster_id=active_cluster.id,
        assigned_member_name="Bhavani",
        assigned_member_age=68,
        status="ACTIVE",
        issued_by_user_id=users[2].id,
        issued_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
    )
    db.add(band1)
    db.add(band2)
    await db.flush()

    # 4. Sample Found Child Case (Demonstrating Last-Known Scan Info and Handover Workflow)
    pa_script = (
        "అత్యవసర ప్రకటన: దయచేసి భక్తులు గమనించగలరు. కోటిలింగాల ఘాట్ పిల్లర్ 14 వద్ద సుమారు 8 సంవత్సరాల వయస్సు గల "
        "ఒక బాలుడు రక్షక సిబ్బంది వద్ద సురక్షితంగా ఉన్నారు. బాలుడు నీలి రంగు టీ-షర్ట్ ధరించి ఉన్నారు. "
        "తల్లిదండ్రులు వెంటనే కోటిలింగాల బంధం హెల్ప్‌డెస్క్ బూత్ #1 వద్దకు విచ్చేయగలరు."
    )
    sample_case = Case(
        case_number="CASE-2027-0101",
        case_type="FOUND_CHILD",
        band_id=band1.band_id,
        cluster_id=active_cluster.id,
        reported_by_name="K. Satyanarayana (Pilgrim)",
        reporter_contact="919123456789",
        reporter_role="FINDER",
        location_name="Kotilingala Ghat - Near Pillar 14",
        latitude=17.0005,
        longitude=81.7778,
        location_accuracy=12.5,
        location_type="GPS",
        status="OPEN",
        assigned_to_user_id=users[1].id,
        assigned_to_name=users[1].full_name,
        bolo_details_json=json.dumps({"clothing": "Blue t-shirt, brown sandals", "age": 8}),
        telugu_announcement_script=pa_script
    )
    db.add(sample_case)
    await db.flush()

    # Notification attempt for the case
    notif = NotificationAttempt(
        case_id=sample_case.id,
        cluster_id=active_cluster.id,
        recipient_phone=active_cluster.primary_phone,
        channel="WHATSAPP",
        status="DELIVERED",
        message_content=(
            f"🚨 BANDHAM ALERT: A member of your family wearing Band {band1.band_id} has been brought to "
            f"Kotilingala Ghat Helpdesk Booth #1. Please attend with your secret Release PIN."
        ),
        initiated_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15),
        delivered_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=14)
    )
    db.add(notif)

    # Scan log recording the last-known scan
    scan = ScanLog(
        band_id=band1.band_id,
        ip_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        latitude=17.0005,
        longitude=81.7778,
        accuracy=12.5,
        manual_location="Kotilingala Ghat - Pillar 14",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )
    db.add(scan)

    # 5. Sample Sanitation Tickets
    san_tickets = [
        SanitationTicket(
            ticket_number="SAN-2027-0041",
            facility_id="TOILET-KOTI-02",
            facility_name="Kotilingala Ghat Block 2 (Men/Women)",
            ghat_name="Kotilingala Ghat",
            issue_type="OVERFLOW",
            priority="URGENT",
            status="ASSIGNED",
            reported_via="WHATSAPP",
            reporter_phone="919876543201",
            description="Drain overflow reported near cubicle 4.",
            assigned_team="Municipal Rapid Clean Team A"
        ),
        SanitationTicket(
            ticket_number="SAN-2027-0038",
            facility_id="TOILET-PUSHKAR-01",
            facility_name="Pushkar Ghat Mobile Restrooms",
            ghat_name="Pushkar Ghat",
            issue_type="UNHYGIENIC",
            priority="HIGH",
            status="CLEANED_PENDING_INSPECTION",
            reported_via="QR_SCAN",
            reporter_phone="919876543202",
            description="Litter and dirty floor.",
            assigned_team="Municipal Clean Team C",
            cleaner_notes="Washed, disinfected with bleaching powder, water tanks refilled.",
            after_photo_url="https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=400&q=80"
        )
    ]
    for s in san_tickets:
        db.add(s)

    # 6. Verified Rate Cards (Pushkaralu 2027 Prototype Sample Data)
    rates = [
        RateCard(
            category="BOAT_RIDE",
            service_name="[SAMPLE] Standard Ghat Ferry",
            approved_rate=50.0,
            unit="per person / round trip",
            effective_date="Pushkaralu Season 2027 [SAMPLE PROTOTYPE]",
            verified_by_authority="Water Transport Authority [SAMPLE]",
            notes="Life jacket mandatory. Child below 5 years free. [SAMPLE DATA]"
        ),
        RateCard(
            category="BOAT_RIDE",
            service_name="[SAMPLE] Havelock Bridge Heritage Scenic Tour (30 min)",
            approved_rate=150.0,
            unit="per person",
            effective_date="Pushkaralu Season 2027 [SAMPLE PROTOTYPE]",
            verified_by_authority="AP Tourism Development Corporation [SAMPLE]",
            notes="Licensed tourist catamaran boats with life-guards. [SAMPLE DATA]"
        ),
        RateCard(
            category="AUTO_RICKSHAW",
            service_name="[SAMPLE] Rajahmundry Railway Station to Pushkar Ghat",
            approved_rate=60.0,
            unit="flat fare (up to 3 passengers)",
            effective_date="Pushkaralu Season 2027 [SAMPLE PROTOTYPE]",
            verified_by_authority="Regional Transport Authority (RTA) [SAMPLE]",
            notes="Prepaid auto slip available at Station Exit. [SAMPLE DATA]"
        ),
        RateCard(
            category="AUTO_RICKSHAW",
            service_name="[SAMPLE] Kotilingala Ghat to Central APSRTC Bus Station",
            approved_rate=80.0,
            unit="flat fare (up to 3 passengers)",
            effective_date="Pushkaralu Season 2027 [SAMPLE PROTOTYPE]",
            verified_by_authority="Regional Transport Authority (RTA) [SAMPLE]",
            notes="Official meter/prepaid tariff. [SAMPLE DATA]"
        ),
        RateCard(
            category="CLOAKROOM",
            service_name="[SAMPLE] Pilgrim Bag Storage",
            approved_rate=20.0,
            unit="per bag / 12 hours",
            effective_date="Pushkaralu Season 2027 [SAMPLE PROTOTYPE]",
            verified_by_authority="Municipal Corporation [SAMPLE]",
            notes="Tokens issued with digital photo receipt. [SAMPLE DATA]"
        )
    ]
    for r in rates:
        db.add(r)

    # 7. Sample Scam / Overcharging Report
    scam = ScamReport(
        report_number="SCAM-2027-0019",
        service_category="AUTO_RICKSHAW",
        service_provider_identifier="AP 05 TX 9182",
        demanded_amount=250.0,
        official_amount=60.0,
        location="Rajahmundry Railway Station West Gate",
        details="Driver refused to accept official prepaid rate and insisted on ₹250 for Pushkar Ghat.",
        reporter_phone="919701234567",
        status="ENFORCEMENT_NOTIFIED",
        action_taken="Forwarded to Traffic Police Sub-Inspector on duty at Station Circle."
    )
    db.add(scam)

    await db.commit()
