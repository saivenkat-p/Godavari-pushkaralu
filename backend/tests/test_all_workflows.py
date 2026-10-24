import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from backend.app.main import app
from backend.app.core.database import engine, Base, AsyncSessionLocal
from backend.app.core.seed_data import seed_database
from backend.app.services.whatsapp_service import WhatsAppService


@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    yield


@pytest.mark.asyncio
async def test_criterion_1_pilgrim_messages_whatsapp():
    """1. A pilgrim messages the WhatsApp assistant and receives a valid reply."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Send greeting in Telugu
        response = await client.post("/api/simulator/chat", json={
            "phone_number": "919999888801",
            "message_text": "నమస్కారం"
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["replies"]) > 0
        assert "బంధం" in data["replies"][0] or "Bandham" in data["replies"][0]


@pytest.mark.asyncio
async def test_criterion_2_and_3_whatsapp_registration_to_dashboard():
    """
    2. A pilgrim begins family registration through WhatsApp.
    3. The pending registration appears in the registration dashboard.
    """
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        phone = "919999888802"
        # Reset session
        await client.post(f"/api/simulator/reset?phone_number={phone}")

        # Choose 1 (Registration)
        r1 = await client.post("/api/simulator/chat", json={"phone_number": phone, "message_text": "1"})
        assert r1.status_code == 200

        # Give Consent "YES"
        r2 = await client.post("/api/simulator/chat", json={"phone_number": phone, "message_text": "YES"})
        assert r2.status_code == 200

        # Guardian Name
        r3 = await client.post("/api/simulator/chat", json={"phone_number": phone, "message_text": "Murali Krishna"})
        assert r3.status_code == 200

        # Backup Phone
        r4 = await client.post("/api/simulator/chat", json={"phone_number": phone, "message_text": "919999888899"})
        assert r4.status_code == 200

        # Wristbands needed
        r5 = await client.post("/api/simulator/chat", json={"phone_number": phone, "message_text": "3"})
        assert r5.status_code == 200

        # Member details -> Triggers pending cluster creation
        r6 = await client.post("/api/simulator/chat", json={"phone_number": phone, "message_text": "Kavitha (Wife), Aditya (Child age 6)"})
        assert r6.status_code == 200
        reply = r6.json()["replies"][0]
        assert "REG-" in reply

        # Now login as Registration Operator and check Pending list
        login_res = await client.post("/api/auth/login", json={
            "username": "reg_operator",
            "password": "Register@2027"
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check pending list
        pending_res = await client.get("/api/registration/pending", headers=headers)
        assert pending_res.status_code == 200
        pending_list = pending_res.json()
        matching = [c for c in pending_list if c["primary_guardian_name"] == "Murali Krishna"]
        assert len(matching) > 0
        assert matching[0]["status"] == "PENDING_VERIFICATION"


@pytest.mark.asyncio
async def test_criterion_4_and_5_verify_and_issue_bands():
    """
    4. An operator verifies the registration and generates QR wristbands.
    5. The operator prints the QR labels and records issuance.
    """
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_res = await client.post("/api/auth/login", json={
            "username": "reg_operator",
            "password": "Register@2027"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Claim seed pending cluster REG-782104
        claim_res = await client.post("/api/registration/claim-pending/REG-782104", headers=headers)
        assert claim_res.status_code == 200
        claim_data = claim_res.json()
        assert claim_data["status"] == "ISSUED"
        assert len(claim_data["bands"]) == 3
        band_id = claim_data["bands"][0]["band_id"]
        assert band_id.startswith("BND-")
        assert "release_pin" in claim_data

        # Print / View Label for the issued band
        label_res = await client.get(f"/api/registration/bands/{band_id}/label", headers=headers)
        assert label_res.status_code == 200
        label_data = label_res.json()
        assert label_data["band_id"] == band_id
        assert label_data["qr_image_data"].startswith("data:image/png;base64,")
        # Safeguard: Verify no phone numbers or personal names in label
        assert "919876543210" not in str(label_data)


@pytest.mark.asyncio
async def test_criterion_6_7_8_qr_scan_and_found_child():
    """
    6. Scanning a QR opens the public assistance flow.
    7. A found-child report creates a real database record.
    8. The guardian-alert attempt appears in the authorized helpdesk dashboard.
    """
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        band_id = "BND-8F32A1C9"  # Active seed band

        # 6. Public QR Scan
        scan_res = await client.get(f"/api/scan/{band_id}")
        assert scan_res.status_code == 200
        scan_data = scan_res.json()
        assert scan_data["band_id"] == band_id
        assert len(scan_data["safe_instructions"]) > 0
        # Safeguard: No parent names or phone numbers exposed
        assert "Subba Rao" not in str(scan_data)
        assert "919848022338" not in str(scan_data)

        # 7. Finder reports found child
        report_res = await client.post(f"/api/scan/{band_id}/report-found", json={
            "band_id": band_id,
            "finder_name": "Raju (Pilgrim)",
            "finder_contact": "919444555666",
            "location_name": "Kotilingala Ghat Pillar 12",
            "location_type": "MANUAL"
        })
        assert report_res.status_code == 200
        report_data = report_res.json()
        assert "case_number" in report_data
        case_no = report_data["case_number"]

        # 8. Check that case and guardian alert attempt appear in Helpdesk
        login_res = await client.post("/api/auth/login", json={
            "username": "helpdesk_operator",
            "password": "Helpdesk@2027"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        cases_res = await client.get(f"/api/cases?search={case_no}", headers=headers)
        assert cases_res.status_code == 200
        cases_list = cases_res.json()
        assert len(cases_list) > 0
        assert cases_list[0]["case_number"] == case_no
        assert len(cases_list[0]["notification_attempts"]) > 0
        assert cases_list[0]["notification_attempts"][0]["recipient_phone"] == "919848022338"


@pytest.mark.asyncio
async def test_criterion_9_case_update_and_verified_handover():
    """9. An authorized operator can update and resolve the case after the required verification."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/auth/login", json={
            "username": "helpdesk_operator",
            "password": "Helpdesk@2027"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Seed case is CASE-2027-0101 (cluster PIN is 4829)
        # Attempt handover with wrong PIN
        bad_pin_res = await client.post("/api/cases/1/verify-handover", headers=headers, json={
            "pin": "0000",
            "witness_staff_name": "Officer K. Lakshmi",
            "guardian_name_verified": "Subba Rao",
            "guardian_phone_verified": "919848022338",
            "notes": "Testing incorrect PIN lockout"
        })
        assert bad_pin_res.status_code == 400

        # Attempt handover with valid PIN (4829)
        good_pin_res = await client.post("/api/cases/1/verify-handover", headers=headers, json={
            "pin": "4829",
            "witness_staff_name": "Officer K. Lakshmi",
            "guardian_name_verified": "Subba Rao",
            "guardian_phone_verified": "919848022338",
            "notes": "Verified parent photo ID and relationship. Child safely reunited."
        })
        assert good_pin_res.status_code == 200
        assert good_pin_res.json()["status"] == "HANDOVER_AUTHORIZED_AND_COMPLETED"


@pytest.mark.asyncio
async def test_criterion_10_unauthorized_access_restriction():
    """10. Unauthorized users cannot access restricted family records."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Anonymous attempt to access cases
        anon_res = await client.get("/api/cases")
        assert anon_res.status_code == 401

        # Sanitation supervisor attempting to access registration or child cases
        san_login = await client.post("/api/auth/login", json={
            "username": "sanitation_lead",
            "password": "Sanitation@2027"
        })
        san_token = san_login.json()["access_token"]
        san_headers = {"Authorization": f"Bearer {san_token}"}

        # Should be forbidden (403)
        restricted_res = await client.get("/api/cases", headers=san_headers)
        assert restricted_res.status_code == 403


@pytest.mark.asyncio
async def test_criterion_11_sanitation_and_verified_services():
    """11. The sanitation and verified-services workflows function end to end."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Public creates sanitation ticket
        san_create = await client.post("/api/sanitation/tickets", json={
            "facility_id": "TOILET-SARAS-01",
            "facility_name": "Saraswati Ghat Restroom",
            "ghat_name": "Saraswati Ghat",
            "issue_type": "NO_WATER",
            "priority": "HIGH",
            "description": "Tanks empty at block 1"
        })
        assert san_create.status_code == 200
        ticket = san_create.json()
        assert ticket["ticket_number"].startswith("SAN-2027-")

        # Public views official verified rate cards
        rates_res = await client.get("/api/services/rate-cards")
        assert rates_res.status_code == 200
        rates = rates_res.json()
        assert len(rates) > 0
        assert any(r["category"] == "BOAT_RIDE" for r in rates)

        # Public reports overcharging scam
        scam_res = await client.post("/api/services/scam-reports", json={
            "service_category": "BOAT_RIDE",
            "service_provider_identifier": "Boat #14",
            "demanded_amount": 200.0,
            "official_amount": 50.0,
            "location": "Pushkar Ghat",
            "details": "Operator insisted on ₹200 despite official ₹50 card."
        })
        assert scam_res.status_code == 200
        assert scam_res.json()["report_number"].startswith("SCAM-2027-")


@pytest.mark.asyncio
async def test_criterion_12_simulation_vs_real_whatsapp_distinction():
    """12. Real WhatsApp testing is explicitly distinguished from simulated testing."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health_res = await client.get("/api/health")
        assert health_res.status_code == 200
        health = health_res.json()
        assert "simulation_mode" in health
        assert "whatsapp_api_configured" in health

        # Outbound call in simulation mode returns SIMULATED_SUCCESS
        outbound = await WhatsAppService.send_text_message("919999000111", "Test Notification")
        assert outbound["status"] == "SIMULATED_SUCCESS"
