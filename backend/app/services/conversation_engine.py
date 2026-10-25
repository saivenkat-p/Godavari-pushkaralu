import json
import re
import secrets
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.models import (
    ConversationSession, FamilyCluster, Band, Case, SanitationTicket, RateCard, ScamReport, NotificationAttempt
)


def is_valid_guardian_name(name_text: str) -> bool:
    """
    Guardian Name validation:
    - Reject purely numeric inputs (like "123").
    - Reject short gibberish or single/double character inputs (like "sx", "a", "77").
    - Require at least 3 characters.
    - If Latin alphabet, require at least one vowel to prevent consonant gibberish like "sx", "qwe", "zzx".
    - Reject single repeated characters like "aaa", "xxx".
    """
    clean = name_text.strip()
    if not clean or clean.isdigit() or len(clean) < 3:
        return False
    if len(set(clean.lower())) == 1:
        return False
    letters = re.findall(r'[a-zA-Z\u0C00-\u0C7F\u0900-\u097F]', clean)
    if len(letters) < 3:
        return False
    # If Latin/English alphabet, require at least one vowel
    latin_letters = re.findall(r'[a-zA-Z]', clean)
    if latin_letters:
        if not re.search(r'[aeiouAEIOU]', clean):
            return False
    return True


def is_valid_backup_phone(phone_text: str) -> Tuple[bool, bool, str]:
    """
    Backup Phone Number validation:
    - Reject invalid numbers like "945".
    - Strictly validate for a valid 10-digit Indian mobile number (starting with 6-9, optional +91/91 prefix)
    - OR the exact word "SKIP" / "స్కిప్" / "0" / "no" / "వద్దు" / "లేదు" / "नहीं".
    Returns (is_valid, is_skip, sanitized_number).
    """
    clean = phone_text.strip()
    clean_lower = clean.lower()
    skip_keywords = ["skip", "స్కిప్", "0", "no", "వద్దు", "లేదు", "नहीं", "skip phone", "none"]
    if clean_lower in skip_keywords:
        return True, True, ""
    
    digits = re.sub(r'[\s\-\(\)\+]', '', clean)
    if not digits.isdigit():
        return False, False, ""
    
    if len(digits) == 10 and digits[0] in "6789":
        return True, False, digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return True, False, digits[2:]
    
    return False, False, ""


def is_valid_band_count(count_text: str) -> Tuple[bool, int]:
    """
    Wristband Count validation:
    - Reject "000", negative numbers, or numbers > 6.
    - Do NOT silently default "000" to 1.
    - Strictly integer between 1 and 6.
    """
    clean = count_text.strip()
    if clean in ["1", "2", "3", "4", "5", "6"]:
        return True, int(clean)
    return False, 0


def is_valid_member_visual_details(member_text: str) -> Tuple[bool, bool, bool]:
    """
    Member Details & Visual Recovery validation:
    Returns (is_valid, is_skip, is_photo_query).
    - If user asks about photos/selfies: is_photo_query=True
    - If user types SKIP, 0, teledu, dont know, later, time waste: is_skip=True, is_valid=True
    - If user provides member names/details: is_valid=True
    """
    clean = member_text.strip()
    clean_lower = clean.lower()

    # 1. Photo / Selfie query detection
    photo_keywords = ["pic", "photo", "selfie", "ఫోటో", "పిక్", "చిత్రం", "फोटो", "तस्वीर", "selfi", "camera"]
    if any(k in clean_lower for k in photo_keywords):
        return False, False, True

    # 2. Skip / Teledu / Stall completion
    skip_keywords = [
        "skip", "స్కిప్", "0", "teledu", "తెలీదు", "తెలియదు", "వద్దు", "dont know", "don't know",
        "no", "లేదు", "time waste", "టైం వేస్ట్", "తరువాత", "later", "stall", "స్టాల్", "पता नहीं", "बाद में", "none"
    ]
    if clean_lower in skip_keywords or any(clean_lower.startswith(k) for k in ["skip", "teledu", "dont know", "don't know", "time waste"]):
        return True, True, False

    # 3. Reject purely numeric or empty
    if not clean or clean.isdigit():
        return False, False, False

    # 4. Require at least one valid name (letters >= 2)
    letters = re.findall(r'[a-zA-Z\u0C00-\u0C7F\u0900-\u097F]', clean)
    if len(letters) < 2:
        return False, False, False

    return True, False, False


def is_valid_missing_details(text: str) -> bool:
    """
    Validates that a reported missing person description is actionable:
    - Rejects single words like 'sai', 'kid', 'child', or short strings (< 6 chars).
    - Rejects pure name labels without descriptors like 'name ; sai', 'name is sai', 'boy sai'.
    - Requires at least 2 alphanumeric words.
    - Requires AT LEAST ONE descriptor:
        1. Age indicator (e.g. digits 1-99, 'age', 'years', 'yr', 'వయస్సు', 'సంవత్సరాల', 'उम्र', 'साल')
        2. Clothing / appearance / color / physical feature:
           ('shirt', 'pant', 'tshirt', 'dress', 'saree', 'frock', 'kurta', 'shorts', 'yellow', 'red', 'blue', 'white',
            'black', 'green', 'pink', 'orange', 'sandals', 'shoes', 'chappal', 'slippers', 'cap', 'height', 'ft', 'feet', 'inch',
            'చొక్కా', 'చొక్క', 'ప్యాంట్', 'చీర', 'డ్రెస్', 'లంగా', 'పసుపు', 'ఎరుపు', 'నీలం', 'తెలుపు', 'నలుపు', 'పచ్చ', 'గులాబీ', 'రంగు', 'చెప్పులు', 'ఎత్తు', 'అడుగులు',
            'कमीज', 'पैंट', 'साड़ी', 'कुर्ता', 'पीली', 'लाल', 'नीली', 'सफेद', 'काली', 'हरी', 'रंग', 'कद', 'फीट', 'चप्पल')
        3. Location indicator:
           ('ghat', 'pillar', 'booth', 'gate', 'bridge', 'counter', 'station', 'temple', 'railway', 'bus', 'kotilingala', 'pushkar', 'saraswati', 'markandeya', 'kovvur',
            'ఘాట్', 'పిల్లర్', 'గేట్', 'బూత్', 'కౌంటర్', 'బ్రిడ్జి', 'గుడి', 'స్టేషన్', 'కోటిలింగాల', 'పుష్కర', 'సరస్వతి', 'మార్కండేయ', 'కొవ్వూరు',
            'घाट', 'पिलर', 'गेट', 'बूथ', 'काउंटर', 'पुल', 'स्टेशन', 'मंदिर')
    """
    clean = text.strip()
    if not clean or len(clean) < 6:
        return False

    words = re.findall(r'[a-zA-Z\u0C00-\u0C7F\u0900-\u097F0-9]+', clean)
    if len(words) < 2:
        return False

    clean_lower = clean.lower()

    # Reject 'name ; sai', 'name is sai', 'name: sai', 'పేరు : సాయి'
    if re.fullmatch(r'(name|పేరు|naam|నామ్)\s*[:;\-\s]+\w+', clean_lower):
        return False

    # Check for age digits (1-2 digit number)
    has_age_digits = bool(re.search(r'\b\d{1,2}\b', clean))
    age_terms = ["age", "వయస్సు", "ఉమ్ర", "उम्र", "year", "yr", "సంవత్సరాలు", "సంవత్సరాల", "साल", "months", "నెలలు"]
    has_age = has_age_digits or any(a in clean_lower for a in age_terms)

    clothing_features = [
        "shirt", "pant", "tshirt", "t-shirt", "dress", "saree", "frock", "kurta", "shorts",
        "yellow", "red", "blue", "white", "black", "green", "pink", "orange", "color", "colour",
        "sandals", "shoes", "chappal", "slippers", "cap", "glasses", "height", "ft", "feet", "inch",
        "చొక్కా", "చొక్క", "ప్యాంట్", "చీర", "డ్రెస్", "లంగా", "ఫ్రాక్", "కుర్తా",
        "పసుపు", "ఎరుపు", "నీలం", "తెలుపు", "నలుపు", "పచ్చ", "గులాబీ", "నారింజ", "రంగు",
        "చెప్పులు", "బూట్లు", "టోపీ", "కళ్లద్దాలు", "ఎత్తు", "అడుగులు",
        "कमीज", "पैंट", "साड़ी", "कुर्ता", "फ्रॉक", "पीली", "लाल", "नीली", "सफेद", "काली", "हरी", "गुलाबी", "रंग",
        "चप्पल", "जूते", "टोपी", "चश्मा", "कद", "ऊंचाई", "फीट"
    ]
    has_clothing = any(c in clean_lower for c in clothing_features)

    locations = [
        "ghat", "pillar", "booth", "gate", "bridge", "counter", "station", "temple", "railway", "bus",
        "kotilingala", "pushkar", "saraswati", "markandeya", "kovvur",
        "ఘాట్", "పిల్లర్", "గేట్", "బూత్", "కౌంటర్", "బ్రిడ్జి", "గుడి", "స్టేషన్", "రైల్వే", "బస్",
        "కోటిలింగాల", "పుష్కర", "సరస్వతి", "మార్కండేయ", "కొవ్వూరు",
        "घाट", "पिलर", "गेट", "बूथ", "काउंटर", "पुल", "स्टेशन", "मंदिर"
    ]
    has_location = any(loc in clean_lower for loc in locations)

    return has_clothing or has_location or (has_age and len(words) >= 4)



TEXTS = {
    "en": {
        "welcome": (
            "🙏 *Welcome to Godavari Pushkaralu 2027 Bandham Assistant!*\n\n"
            "[PILOT PROTOTYPE - SAMPLE DATA]\n"
            "Citizen Safety & Pilgrim Support Assistant for Rajahmundry & Kovvur (Pilot Demonstration).\n\n"
            "Please choose an option (reply with number or text):\n"
            "1️⃣ *Family Safety / Bandham QR Registration*\n"
            "2️⃣ *Report a Missing Child / Family Member*\n"
            "3️⃣ *I Found a Lost Child*\n"
            "4️⃣ *Find Ghats & Public Facilities*\n"
            "5️⃣ *Toilets & Sanitation Report*\n"
            "6️⃣ *Services & Approved Rates [SAMPLE DATA]*\n"
            "7️⃣ *Report Overcharging or Scam*\n"
            "8️⃣ *Emergency Helpdesk & Police Support*\n"
            "9️⃣ *Change Language / భాష మార్చండి / भाषा बदलें*\n\n"
            "_Tip: You can also type natural questions like 'where is Pushkar ghat' or 'report lost child' anytime._"
        ),
        "menu_hint": "\n\n_Reply *0* or *MENU* at any time to return to the main menu._",
        "lang_selection": (
            "🌐 *Select Your Preferred Language / భాషను ఎంచుకోండి / भाषा चुनें:*\n\n"
            "1. తెలుగు (Telugu)\n"
            "2. English\n"
            "3. हिन्दी (Hindi)\n\n"
            "_Reply with 1, 2, or 3._"
        ),
        "lang_updated": "Language set to English.",
        "reg_intro": (
            "🛡️ *Bandham QR Family Protection Registration*\n\n"
            "Bandham QR links your family wristbands securely in our emergency grid. "
            "If a child or elderly relative gets separated, authorized helpdesks and scanners can instantly alert you *without ever exposing your phone number publicly*.\n\n"
            "🔒 *Data Consent*: We collect only your name, contact numbers, and registered dependents. Data is retained only for Pushkaralu safety operations.\n\n"
            "Do you consent to proceed with registration?\n"
            "Reply *YES* to continue, or *0* to cancel."
        ),
        "reg_ask_guardian_name": "Please enter the *Primary Guardian's Full Name* (letters only, at least 3 characters):\n\n_(Reply *0* or *MENU* to cancel)_",
        "invalid_guardian_name": "⚠️ *Invalid Guardian Name*: Please enter a valid full name with at least 3 letters (e.g., Murali Krishna, Ramesh Rao):\n\n_(Reply *0* or *MENU* to cancel)_",
        "reg_ask_backup_phone": "Please enter an *Alternative / Backup Phone Number* (10-digit Indian mobile number, e.g. 9848022338, or reply *SKIP*):\n\n_(Reply *0* or *MENU* to cancel)_",
        "invalid_backup_phone": "⚠️ *Invalid Backup Phone*: Please enter a valid 10-digit Indian mobile number (starting with 6-9, e.g. 9848022338) or reply *SKIP* (or *0*):\n\n_(Reply *0* or *MENU* to cancel)_",
        "reg_ask_bands_count": "How many Bandham wristbands does your family need? (Enter an integer from 1 to 6):\n\n_(Reply *0* or *MENU* to cancel)_",
        "invalid_bands_count": "⚠️ *Invalid Wristband Count*: Please enter a single digit from 1 to 6 (maximum 6 wristbands per family cluster):\n\n_(Reply *0* or *MENU* to cancel)_",
        "photo_guidance": (
            "📸 *Photo / Selfie Information*:\n"
            "No need to upload photos on WhatsApp. When you arrive at the Bandham stall at the ghat, our staff will capture photos directly into the system.\n\n"
            "For now, please enter family member names, or reply *SKIP* (or *0*) to complete all details at the stall.\n\n"
            "_(Reply *0* or *MENU* to cancel)_"
        ),
        "reg_ask_members": (
            "Please provide the *Names and Clothing Details* of family members (e.g., 'Aarav, age 7, yellow shirt'):\n"
            "_Or reply *SKIP* to complete these visual details directly at the physical stall._\n\n"
            "_(Reply *0* or *MENU* to cancel)_"
        ),
        "invalid_members_details": (
            "⚠️ *Family Member Details*:\n"
            "Please enter the names of family members (e.g. 'Aarav, age 7, yellow shirt'), or reply *SKIP* to provide these details directly at the ghat stall.\n\n"
            "_(Reply *0* or *MENU* to cancel)_"
        ),
        "reg_success": (
            "✅ *Pending Registration Created Successfully!*\n\n"
            "📋 *Registration Reference*: *{ref}*\n"
            "👤 *Guardian*: {name}\n"
            "📞 *Primary Contact*: {phone}\n"
            "🏷️ *Wristbands Requested*: {count}\n\n"
            "⚠️ *Important Next Step*: Wristbands are *not yet active*. Please visit any authorized *Bandham QR Stall* at Kotilingala Ghat, Pushkar Ghat, or Kovvur Main Ghat with reference *{ref}*. Our staff will verify your contact, hand over physical tamper-evident bands, and issue your private 6-digit *Handover Release PIN*."
        ),
        "missing_child_intro": (
            "🚨 *EMERGENCY: Report a Missing Child / Family Member*\n\n"
            "If you are at the ghat right now, please stay calm and approach the nearest *Police Helpdesk* immediately.\n\n"
            "Does the missing person have a Bandham QR wristband?\n"
            "1. Yes, I have the Band ID or Cluster Reference\n"
            "2. No band / Don't have the ID\n\n"
            "_Reply 1 or 2, or reply 0 to cancel._"
        ),
        "missing_ask_band_id": "Please enter the *Band ID* (e.g. BND-XXXXXXXX) or *Registration Reference*:",
        "missing_ask_details": (
            "Please provide details: *Child's Name, Approximate Age, Clothing Color/Type*, and *Last Seen Location* at the ghats (e.g., 'Sai, age 7, yellow t-shirt, Kotilingala Pillar 14'):\n\n"
            "_(Reply *0* or *MENU* to cancel)_"
        ),
        "invalid_missing_details": (
            "⚠️ *More Details Required*:\n"
            "In a crowd of millions, searching by a single name alone is impossible.\n"
            "Please provide child's approximate age, clothing color/type, and last seen location:\n\n"
            "_Example: 'Sai, age 7, yellow t-shirt, Kotilingala Ghat Pillar 14'_\n\n"
            "_(Reply *0* or *MENU* to cancel)_"
        ),
        "missing_case_created": (
            "🚨 *URGENT EMERGENCY ALERT ISSUED*\n\n"
            "Case Number: *{case_no}*\n"
            "Child Details: {details}\n"
            "Status: *ACTIVE BOLO DISPATCHED TO ALL HELPDESK RUNNERS & POLICE POSTS*\n\n"
            "📢 A public address announcement script has been generated for ghat operators.\n"
            "📍 *Immediate Action*: Please report to the nearest *Police Control Booth* or *Bandham Helpdesk #1 (Kotilingala Ghat)* immediately. Keep this WhatsApp chat open for updates."
        ),
        "case_followup_hint": (
            "ℹ️ *Case {case_no} is ACTIVE*.\n"
            "You can type additional details anytime (e.g. 'wearing blue sandals'), or ask 'how do you find' / 'where to go'.\n\n"
            "_(Reply *0* or *MENU* when done)_"
        ),
        "how_search_works": (
            "ℹ️ *How Lost Person Search Works at Godavari Pushkaralu*:\n\n"
            "1. 📢 *Public Address System*: An automated Telugu PA announcement script is broadcast across 40+ high-power ghat loudspeakers.\n"
            "2. 🏃 *200+ Rescue Runners*: Details and visual descriptions are instantly pushed to on-duty police runners and volunteers.\n"
            "3. 👮 *Police Control Posts*: Exit barricades and transit points (bus/train stations) are placed on high alert.\n\n"
            "📍 *Action Required*: Please walk immediately to the nearest *Police Helpdesk Booth* or *Bandham Stall* at Kotilingala or Pushkar Ghat with a photo of the child for accelerated identification.\n\n"
            "_Type any extra details here to update your case, or reply *0* for main menu._"
        ),
        "next_steps_instructions": (
            "📍 *Immediate Next Steps for Family*:\n\n"
            "1. Go immediately to the nearest *Police Control Booth* or *Kotilingala Ghat Helpdesk #1*.\n"
            "2. Keep your mobile phone line free for calls from the police or finder.\n"
            "3. If you have a photograph of the child on your phone, show it to the officer on duty so runners can match visual features.\n\n"
            "_Reply *0* or *MENU* to return to the main menu._"
        ),
        "case_updated": "✅ *Case {case_no} Updated*: Additional note '{update}' has been logged and dispatched to rescue teams.\n\n_(Reply *0* or *MENU* for main menu)_",
        "case_active_reminder": "🚨 *Your Case {case_no} is ACTIVE*. Please proceed to the nearest Police Helpdesk immediately. You can type more details to update your report, or reply *0* for main menu.",
        "found_child_intro": (
            "⚠️ *CHILD SAFEGUARDING INSTRUCTION*\n\n"
            "Thank you for helping. *CRITICAL SAFETY NOTICE*:\n"
            "1. NEVER hand the child to an unverified member of the public.\n"
            "2. Keep the child safe and calm.\n"
            "3. If the child has a Bandham wristband, scan the QR code on the band or enter the 8-character Band ID printed on it.\n\n"
            "Does the child have a Bandham wristband?\n"
            "Reply with the *Band ID* (e.g., BND-XXXXXX), or reply *NO* if there is no band."
        ),
        "found_ask_location": (
            "Where are you currently with the child?\n"
            "1. Kotilingala Ghat (Helpdesk Booth 1)\n"
            "2. Pushkar Ghat (Helpdesk Booth 2)\n"
            "3. Saraswati Ghat\n"
            "4. Markandeya Ghat\n"
            "5. Kovvur Goshpada Kshetram Ghat\n"
            "6. Other location (type description)\n\n"
            "_Reply with number 1-5 or your exact pillar/landmark._"
        ),
        "found_child_reported": (
            "✅ *REPORT LOGGED IN CENTRAL OPERATIONS*\n\n"
            "Case Number: *{case_no}*\n"
            "Assigned Helpdesk: {location}\n\n"
            "Our nearest rescue officer has been notified and is proceeding to your location. "
            "Please escort the child directly to the nearest uniformed Police Officer or Bandham Helpdesk Booth."
        ),
        "ghats_info": (
            "🌊 *Godavari Pushkaralu 2027 Major Ghats & Facilities [SAMPLE DATA]*:\n\n"
            "1. *Kotilingala Ghat (Rajahmundry)*: 3 km long, medical camp, 6 helpdesk booths, lost child center.\n"
            "2. *Pushkar Ghat (Rajahmundry)*: Central holy dip point, Railway station 1.2 km away, mother-care feeding pods.\n"
            "3. *Saraswati Ghat*: Less crowded, elderly assistance ramps, specialized bathing enclosures.\n"
            "4. *Markandeya Ghat*: Near historic temple, dedicated transit parking feeder.\n"
            "5. *Goshpada Kshetram Ghat (Kovvur)*: West Godavari bank, special pilgrim bus terminal.\n\n"
            "_Note: Facility locations are illustrative sample data for prototype demonstration._\n"
            "Need specific directions? Type 'directions to Kotilingala' or reply *0* for main menu."
        ),
        "sanitation_intro": (
            "🧹 *Pushkaralu Sanitation & Cleanliness Dispatch*\n\n"
            "Help keep our holy Godavari clean!\n"
            "1. Report an unclean or overflowing toilet block\n"
            "2. Report water shortage in washrooms\n"
            "3. Report garbage accumulation at ghat\n"
            "4. Scan Toilet Facility QR Code\n\n"
            "_Reply 1, 2, 3, or 4._"
        ),
        "sanitation_ask_location": "Please specify the Ghat and Toilet/Facility ID (e.g. 'Pushkar Ghat Block B' or 'TOILET-KOTI-03'):",
        "sanitation_ticket_created": (
            "✅ *Sanitation Ticket Created: {ticket_no}*\n"
            "Facility: {facility}\n"
            "Priority: High\n\n"
            "Our zonal cleaning team has been dispatched. Supervisor verification is required before closing this ticket. Thank you for your civic contribution!"
        ),
        "rates_info": (
            "📜 *Indicative Service Rates [SAMPLE DATA - NOT OFFICIAL]*\n"
            "(Illustrative Pilot Rates - For Demonstration Only):\n\n"
            "🚤 *Authorized Boat Rides [SAMPLE]*:\n"
            "• Standard Ghat Ferry: ₹50 / person (Life jacket mandatory)\n"
            "• Havelock Bridge Scenic Tour (30 mins): ₹150 / person\n\n"
            "🛺 *Auto-Rickshaw Pre-Fixed Tariffs [SAMPLE]*:\n"
            "• Rajahmundry Station to Pushkar Ghat: ₹60 flat\n"
            "• Kotilingala Ghat to Central Bus Stand: ₹80 flat\n\n"
            "🧳 *Cloakrooms [SAMPLE]*: ₹20 per bag for 12 hours\n"
            "🪔 *Temple Special Darshan*: Regulated counter only.\n\n"
            "⚠️ If anyone demands unauthorized excess rates, reply *7* immediately to report overcharging!"
        ),
        "scam_ask_category": (
            "⚖️ *Report Overcharging or Service Scam*\n"
            "What service was involved?\n"
            "1. Boat / Ferry Ride\n"
            "2. Auto Rickshaw / Taxi\n"
            "3. Cloakroom / Bag Storage\n"
            "4. Puja / Ritual Services\n"
            "5. Accommodation / Food\n\n"
            "_Reply 1-5._"
        ),
        "scam_ask_details": (
            "Please provide details: Vehicle/Boat/Stall number, Amount Demanded vs Official Rate, and Location:"
        ),
        "scam_report_created": (
            "✅ *Scam / Overcharging Report Logged: {report_no}*\n"
            "Details forwarded to the Special Revenue & Enforcement Flying Squad at Rajahmundry. "
            "Inspectors are actively monitoring this sector."
        ),
        "helpdesk_info": (
            "📞 *Pushkaralu Helplines & Emergency Contacts*:\n\n"
            "🚨 *Central Helpline*: 1800-425-2027 [SAMPLE DATA - NOT OFFICIAL]\n"
            "👮 *Police & Child Protection*: 112 [REAL EMERGENCY LINE]\n"
            "🚑 *Medical & Ambulance Control*: 108 / 104 [REAL EMERGENCY LINE]\n"
            "🌊 *River Safety*: 0883-2422099 [SAMPLE DATA]\n\n"
            "Physical Helpdesk Stalls are located along Kotilingala, Pushkar, and Kovvur Ghats. Look for yellow and blue 'BANDHAM QR' signboards."
        ),
        "fallback": "I didn't quite catch that. Reply *0* to see the main menu or choose an option (1-9)."
    },
    "te": {
        "welcome": (
            "🙏 *గోదావరి పుష్కరాలు 2027 బంధం అసిస్టెంట్‌కు స్వాగతం!*\n\n"
            "[పైలట్ ప్రదర్శన - నమూనా సమాచారం / PILOT PROTOTYPE - SAMPLE DATA]\n"
            "రాజమండ్రి మరియు కొవ్వూరు ఘాట్ల వద్ద భక్తుల రక్షణ మరియు సహాయం కొరకు ప్రదర్శన అసిస్టెంట్.\n\n"
            "దయచేసి కింది సేవలలో ఒకదాన్ని ఎంచుకోండి (నంబర్ లేదా టెక్స్ట్ పంపండి):\n"
            "1️⃣ *బంధం క్యూఆర్ (Bandham QR) కుటుంబ నమోదు*\n"
            "2️⃣ *తప్పిపోయిన పిల్లలు / కుటుంబ సభ్యుల అత్యవసర రిపోర్ట్*\n"
            "3️⃣ *తప్పిపోయిన పిల్లవాడు దొరికాడు*\n"
            "4️⃣ *స్నాన ఘాట్లు మరియు ముఖ్య సదుపాయాలు*\n"
            "5️⃣ *మరుగుదొడ్లు మరియు పారిశుధ్య సమస్యల ఫిర్యాదు*\n"
            "6️⃣ *సేవా చార్జీలు మరియు రేట్ల వివరాలు [నిదర్శన సమాచారం - అధికారికం కాదు]*\n"
            "7️⃣ *అదనపు చార్జీలు / మోసాల పై ఫిర్యాదు*\n"
            "8️⃣ *హెల్ప్‌డెస్క్ మరియు పోలీస్ సహాయం*\n"
            "9️⃣ *భాష మార్చండి / Change Language / भाषा बदलें*\n\n"
            "_గమనిక: మీరు 'పుష్కర ఘాట్ ఎక్కడ', 'పిల్లవాడు తప్పిపోయాడు' అని కూడా నేరుగా అడగవచ్చు._"
        ),
        "menu_hint": "\n\n_ప్రధాన మెనూ కోసం ఎప్పుడైనా *0* లేదా *MENU* అని టైప్ చేయండి._",
        "lang_selection": (
            "🌐 *భాషను ఎంచుకోండి / Select Language / भाषा चुनें:*\n\n"
            "1. తెలుగు (Telugu)\n"
            "2. English\n"
            "3. हिन्दी (Hindi)\n\n"
            "_1, 2 లేదా 3 అని రిప్లై ఇవ్వండి._"
        ),
        "lang_updated": "మీ ప్రాధాన్యత భాష తెలుగుగా మార్చబడింది.",
        "reg_intro": (
            "🛡️ *బంధం క్యూఆర్ (Bandham QR) కుటుంబ రక్షణ నమోదు*\n\n"
            "బంధం రిస్ట్‌బ్యాండ్ క్యూఆర్ కోడ్ ద్వారా మీ కుటుంబం ఎల్లప్పుడూ రక్షణలో ఉంటుంది. "
            "జనసమ్మర్దంలో పిల్లలు తప్పిపోతే, మీ ఫోన్ నంబర్ ఇతరులకు బహిర్గతం కాకుండానే అధికారిక హెల్ప్‌డెస్క్ ద్వారా మిమ్మల్ని క్షణాల్లో సంప్రదిస్తారు.\n\n"
            "🔒 *సమ్మతి (Consent)*: మేము మీ పేరు, ఫోన్ నంబర్ మరియు కుటుంబ సభ్యుల సంఖ్యను మాత్రమే సేకరిస్తాము. ఈ సమాచారం పుష్కరాల భద్రత కొరకు మాత్రమే ఉపయోగించబడుతుంది.\n\n"
            "నమోదును కొనసాగించడానికి అంగీకరిస్తున్నారా?\n"
            "*YES* అని సమాధానం ఇవ్వండి, లేదా రద్దు చేయడానికి *0* నొక్కండి."
        ),
        "reg_ask_guardian_name": "దయచేసి *కుటుంబ పెద్ద / సంరక్షకుడి పూర్తి పేరు* నమోదు చేయండి (కనీసం 3 అక్షరాలు):\n\n_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_",
        "invalid_guardian_name": "⚠️ *పేరు సరైనది కాదు*: దయచేసి కనీసం 3 అక్షరాలు గల సరైన పేరును నమోదు చేయండి (కేవలం సంఖ్యలు, ఒకే అక్షరం లేదా అర్ధంలేని అక్షరాలు అంగీకరించబడవు):\n\n_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_",
        "reg_ask_backup_phone": "దయచేసి *మరొక ప్రత్యామ్నాయ ఫోన్ నంబర్* ఇవ్వండి (10 అంకెల మొబైల్ నంబర్ లేదా *SKIP* అని టైప్ చేయండి):\n\n_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_",
        "invalid_backup_phone": "⚠️ *ప్రత్యామ్నాయ ఫోన్ నంబర్ సరైనది కాదు*: దయచేసి 6-9తో ప్రారంభమయ్యే 10 అంకెల మొబైల్ నంబర్ ఇవ్వండి (ఉదా: 9848022338) లేదా *SKIP* (లేదా *0*) అని టైప్ చేయండి:\n\n_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_",
        "reg_ask_bands_count": "మీ కుటుంబానికి ఎన్ని బంధం రిస్ట్‌బ్యాండ్లు కావాలి? (1 నుండి 6 వరకు సంఖ్య నమోదు చేయండి):\n\n_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_",
        "invalid_bands_count": "⚠️ *రిస్ట్‌బ్యాండ్ల సంఖ్య సరైనది కాదు*: దయచేసి 1 నుండి 6 వరకు మాత్రమే సంఖ్యను నమోదు చేయండి (కుటుంబానికి గరిష్టంగా 6):\n\n_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_",
        "photo_guidance": (
            "📸 *ఫోటో/సెల్ఫీ సమాచారం*:\n"
            "వాట్సాప్ ద్వారా ఫోటోలు పంపనవసరం లేదు. మీరు ఘాట్ వద్ద బంధం స్టాల్‌కు వెళ్ళినప్పుడు మా ఆపరేటర్ వెరిఫై చేసి ఫోటోను నేరుగా సిస్టమ్‌లో భద్రపరుస్తారు.\n\n"
            "ప్రస్తుతానికి సభ్యుల పేర్లు పంపండి, లేదా వివరాలు నేరుగా స్టాల్ వద్ద ఇవ్వడానికి *SKIP* (లేదా *0*) అని టైప్ చేయండి.\n\n"
            "_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_"
        ),
        "reg_ask_members": (
            "దయచేసి కుటుంబ సభ్యుల *పేర్లు మరియు దుస్తుల వివరాలు* నమోదు చేయండి (ఉదా: 'ఆరవ్, వయస్సు 7, పసుపు చొక్కా'):\n"
            "_లేదా ఈ వివరాలను నేరుగా ఘాట్ వద్ద గల స్టాల్‌లో ఇవ్వడానికి *SKIP* అని టైప్ చేయండి._\n\n"
            "_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_"
        ),
        "invalid_members_details": (
            "⚠️ *కుటుంబ సభ్యుల వివరాలు*:\n"
            "దయచేసి సభ్యుల పేర్లు పంపండి (ఉదా: 'ఆరవ్, వయస్సు 7, పసుపు చొక్కా').\n"
            "లేదా ఈ వివరాలు నేరుగా ఘాట్ వద్ద గల స్టాల్‌లో ఇవ్వడానికి *SKIP* అని టైప్ చేయండి.\n\n"
            "_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_"
        ),
        "reg_success": (
            "✅ *రిజిస్ట్రేషన్ నమోదు పూర్తయింది!*\n\n"
            "📋 *రిజిస్ట్రేషన్ రిఫరెన్స్*: *{ref}*\n"
            "👤 *సంరక్షకుడు*: {name}\n"
            "📞 *మొబైల్ నంబర్*: {phone}\n"
            "🏷️ *రిస్ట్‌బ్యాండ్లు*: {count}\n\n"
            "⚠️ *ముఖ్యమైన తదుపరి చర్య*: రిస్ట్‌బ్యాండ్లు ఇంకా యాక్టివేట్ కాలేదు. దయచేసి కోటిలింగాల ఘాట్ లేదా పుష్కర ఘాట్ వద్ద గల అధికారిక *బంధం క్యూఆర్ స్టాల్* వద్దకు వెళ్లి ఈ రిఫరెన్స్ నంబర్ *{ref}* చూపించండి. మా సిబ్బంది మీ నంబర్ ధృవీకరించి, వాటర్‌ప్రూఫ్ రిస్ట్‌బ్యాండ్లు మరియు రహస్య 6-అంకెల *హ్యాండోవర్ పిన్ (PIN)* అందజేస్తారు."
        ),
        "missing_child_intro": (
            "🚨 *అత్యవసరం: తప్పిపోయిన పిల్లల వివరాలు*\n\n"
            "మీరు ప్రస్తుతం ఘాట్ వద్ద ఉన్నట్లయితే ఆందోళన చెందకండి. వెంటనే సమీపంలోని *పోలీస్ హెల్ప్‌డెస్క్* వద్దకు వెళ్లండి.\n\n"
            "తప్పిపోయిన వ్యక్తి వద్ద బంధం రిస్ట్‌బ్యాండ్ ఉందా?\n"
            "1. అవును, బ్యాండ్ ఐడీ లేదా రిఫరెన్స్ ఉంది\n"
            "2. లేదు / బ్యాండ్ ఐడీ తెలియదు\n\n"
            "_1 లేదా 2 అని రిప్లై ఇవ్వండి._"
        ),
        "missing_ask_band_id": "దయచేసి *బ్యాండ్ ఐడీ* (BND-XXXXXXXX) లేదా రిజిస్ట్రేషన్ రిఫరెన్స్ నమోదు చేయండి:",
        "missing_ask_details": (
            "దయచేసి పిల్లల *పేరు, సుమారు వయస్సు, వేసుకున్న దుస్తుల రంగు/రకం* మరియు *చివరిగా చూసిన లొకేషన్* పంపండి (ఉదా: 'సాయి, వయస్సు 7, పసుపు చొక్కా, కోటిలింగాల పిల్లర్ 14'):\n\n"
            "_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_"
        ),
        "invalid_missing_details": (
            "⚠️ *మరిన్ని వివరాలు తప్పనిసరి*:\n"
            "లక్షలాది మంది భక్తుల జనసమ్మర్దంలో కేవలం ఒకే ఒక్క పేరుతో వెతకడం అసాధ్యం.\n"
            "దయచేసి పిల్లల వయస్సు, ధరించిన బట్టల రంగు/రకం మరియు చివరిగా ఎక్కడ చూశారో వివరాలు ఇవ్వండి:\n\n"
            "_ఉదాహరణ: 'సాయి, వయస్సు 7, పసుపు చొక్కా, కోటిలింగాల ఘాట్'_\n\n"
            "_(నమోదు రద్దు చేయడానికి '0' లేదా 'MENU' నొక్కండి)_"
        ),
        "missing_case_created": (
            "🚨 *అత్యవసర మిస్సింగ్ హెచ్చరిక నమోదు చేయబడింది*\n\n"
            "కేస్ నంబర్: *{case_no}*\n"
            "వివరాలు: {details}\n"
            "స్థితి: *అన్ని ఘాట్ల హెల్ప్‌డెస్క్ రన్నర్లు మరియు పోలీస్ సిబ్బందికి BOLO జారీ చేయబడింది*\n\n"
            "📢 పబ్లిక్ అడ్రస్ సిస్టమ్ ద్వారా ప్రకటన చేయడానికి అధికారిక స్క్రిప్ట్ సిద్ధమైంది.\n"
            "📍 *తక్షణ చర్య*: దయచేసి వెంటనే కోటిలింగాల లేదా పుష్కర ఘాట్ వద్ద ఉన్న *పోలీస్ కంట్రోల్ బూత్* వద్దకు వెళ్లండి."
        ),
        "case_followup_hint": (
            "ℹ️ *కేస్ {case_no} ప్రస్తుతం యాక్టివ్‌గా ఉంది*.\n"
            "మీరు పిల్లల గురించి మరిన్ని వివరాలు (ఉదా: 'నీలం రంగు చెప్పులు వేసుకున్నాడు') ఇక్కడ టైప్ చేయవచ్చు, లేదా 'ఎలా వెతుకుతారు' / 'నేను ఎక్కడికి వెళ్ళాలి' అని అడగవచ్చు.\n\n"
            "_(ప్రధాన మెనూ కొరకు '0' లేదా 'MENU' నొక్కండి)_"
        ),
        "how_search_works": (
            "ℹ️ *పుష్కరాలలో పిల్లల గాలింపు ఎలా జరుగుతుంది?*:\n\n"
            "1. 📢 *లౌడ్‌స్పీకర్ అనౌన్స్‌మెంట్‌లు*: మీ కేస్ రిపోర్ట్ అవ్వగానే ఘాట్లలోని 40+ లౌడ్‌స్పీకర్ల ద్వారా అధికారిక తెలుగు ప్రకటన నిరంతరం ప్రసారం చేయబడుతుంది.\n"
            "2. 🏃 *200+ రెస్క్యూ రన్నర్లు*: వివరాలు మరియు దుస్తుల గుర్తులు వెంటనే ఘాట్లలో విధులు నిర్వహించే పోలీస్ రన్నర్లు, వాలంటీర్లకు చేరతాయి.\n"
            "3. 👮 *పోలీస్ కంట్రోల్ బూత్‌లు*: ఘాట్ ఎగ్జిట్ పాయింట్లు, ఆర్టీసీ బస్ స్టేషన్లు మరియు రైల్వే స్టేషన్లలో అలర్ట్ జారీ చేయబడుతుంది.\n\n"
            "📍 *మీరు వెంటనే చేయవలసిన పని*: దయచేసి వెంటనే కోటిలింగాల లేదా పుష్కర ఘాట్ వద్ద ఉన్న *పోలీస్ కంట్రోల్ బూత్* వద్దకు వెళ్ళండి. పిల్లల ఫోటో చూపిస్తే రన్నర్లు మరింత త్వరగా గుర్తిస్తారు.\n\n"
            "_అదనపు వివరాలు ఉంటే ఇక్కడే టైప్ చేయండి, లేదా ప్రధాన మెనూ కొరకు *0* నొక్కండి._"
        ),
        "next_steps_instructions": (
            "📍 *కుటుంబ సభ్యులు వెంటనే చేయవలసిన పనులు*:\n\n"
            "1. వెంటనే సమీపంలోని *పోలీస్ కంట్రోల్ బూత్* లేదా *కోటిలింగాల హెల్ప్‌డెస్క్ #1* వద్దకు వెళ్ళండి.\n"
            "2. మీ ఫోన్ లైన్ ఖాళీగా ఉంచండి (పోలీసులు లేదా రక్షకులు ఫోన్ చేయవచ్చు).\n"
            "3. మీ ఫోన్‌లో పిల్లల ఫోటో ఉంటే డ్యూటీలో ఉన్న పోలీస్ అధికారికి చూపించండి.\n\n"
            "_ప్రధాన మెనూ కొరకు '0' లేదా 'MENU' నొక్కండి._"
        ),
        "case_updated": "✅ *కేస్ {case_no} అప్‌డేట్ చేయబడింది*: అదనపు వివరాలు '{update}' నమోదయ్యాయి మరియు గ్రౌండ్ రెస్క్యూ సిబ్బందికి చేరవేయబడ్డాయి.\n\n_(ప్రధాన మెనూ కొరకు '0' నొక్కండి)_",
        "case_active_reminder": "🚨 *మీ కేస్ {case_no} యాక్టివ్‌గా ఉంది*. దయచేసి వెంటనే సమీప పోలీస్ హెల్ప్‌డెస్క్ వద్దకు వెళ్ళండి. అదనపు వివరాలు నమోదు చేయడానికి ఇక్కడే టైప్ చేయండి, లేదా ప్రధాన మెనూ కొరకు '0' నొక్కండి.",
        "found_child_intro": (
            "⚠️ *పిల్లల భద్రతా హెచ్చరిక*\n\n"
            "సహాయం చేసినందుకు ధన్యవాదాలు. *అత్యంత ముఖ్యమైన భద్రతా నియమం*:\n"
            "1. పిల్లవాడిని ఎట్టి పరిస్థితుల్లోనూ గుర్తుతెలియని వ్యక్తులకు అప్పగించవద్దు.\n"
            "2. పిల్లవాడి వద్ద బంధం రిస్ట్‌బ్యాండ్ ఉన్నట్లయితే, దానిపై ముద్రించిన 8-అంకెల బ్యాండ్ ఐడీని చూడండి.\n\n"
            "పిల్లవాడి వద్ద రిస్ట్‌బ్యాండ్ ఉందా?\n"
            "*బ్యాండ్ ఐడీ* (ఉదా: BND-XXXXXX) పంపండి, లేదా లేకపోతే *NO* అని పంపండి."
        ),
        "found_ask_location": (
            "మీరు ప్రస్తుతం పిల్లవాడితో ఎక్కడున్నారు?\n"
            "1. కోటిలింగాల ఘాట్ (హెల్ప్‌డెస్క్ 1)\n"
            "2. పుష్కర ఘాట్ (హెల్ప్‌డెస్క్ 2)\n"
            "3. సరస్వతి ఘాట్\n"
            "4. మార్కండేయ ఘాట్\n"
            "5. కొవ్వూరు గోష్పాద క్షేత్రం ఘాట్\n"
            "6. ఇతర ప్రాంతం (వివరించండి)\n\n"
            "_1 నుండి 5 వరకు సంఖ్య పంపండి లేదా మీ లొకేషన్ టైప్ చేయండి._"
        ),
        "found_child_reported": (
            "✅ *సమాచారం కంట్రోల్ రూమ్‌కు చేరింది*\n\n"
            "కేస్ నంబర్: *{case_no}*\n"
            "లొకేషన్: {location}\n\n"
            "సమీపంలోని రక్షక సిబ్బంది బయలుదేరారు. దయచేసి పిల్లవాడిని వెంటనే దగ్గరలోని యూనిఫాం పోలీస్ అధికారి లేదా బంధం హెల్ప్‌డెస్క్ వద్దకు తీసుకెళ్లండి."
        ),
        "ghats_info": (
            "🌊 *గోదావరి పుష్కరాలు 2027 ముఖ్య ఘాట్ల వివరాలు [నిదర్శన సమాచారం]*:\n\n"
            "1. *కోటిలింగాల ఘాట్ (రాజమండ్రి)*: 3 కి.మీ పొడవు, 24 గంటల వైద్య శిబిరం, 6 హెల్ప్‌డెస్కులు, బంధం కౌంటర్లు.\n"
            "2. *పుష్కర ఘాట్*: ప్రధాన పవిత్ర స్నాన ఘాట్, రైల్వే స్టేషన్‌కు 1.2 కి.మీ.\n"
            "3. *సరస్వతి ఘాట్*: రద్దీ తక్కువ, వృద్ధులకు ప్రత్యేక ర్యాంప్ సదుపాయం.\n"
            "4. *మార్కండేయ ఘాట్*: పురాతన ఆలయం సమీపంలో, ఉచిత ప్రసాద కేంద్రం.\n"
            "5. *గోష్పాద క్షేత్రం ఘాట్ (కొవ్వూరు)*: పశ్చిమ గోదావరి వైపు ముఖ్య ఘాట్, బస్సు టెర్మినల్."
        ),
        "sanitation_intro": (
            "🧹 *పారిశుధ్య సమస్యల నివేదిక & పరిష్కారం*\n\n"
            "స్వచ్ఛమైన పుష్కరాల కొరకు ఫిర్యాదు నమోదు చేయండి:\n"
            "1. అపరిశుభ్రమైన మరుగుదొడ్లు\n"
            "2. నీటి కొరత\n"
            "3. చెత్త నిండిపోవడం\n"
            "4. శానిటేషన్ క్యూఆర్ కోడ్ స్కాన్ చేయండి\n\n"
            "_1, 2, 3 లేదా 4 అని రిప్లై ఇవ్వండి._"
        ),
        "sanitation_ask_location": "దయచేసి ఘాట్ పేరు మరియు బ్లాక్/టాయిలెట్ ఐడీ తెలపండి (ఉదా: పుష్కర ఘాట్ బ్లాక్ 4):",
        "sanitation_ticket_created": (
            "✅ *పారిశుధ్య టికెట్ నమోదైంది: {ticket_no}*\n"
            "లొకేషన్: {facility}\n\n"
            "మున్సిపల్ స్పెషల్ క్లీనింగ్ టీంకు సమాచారం పంపబడింది. శుభ్రం చేసిన తర్వాత ఫోటో ఆధారంతో మాత్రమే టికెట్ ముగించబడుతుంది."
        ),
        "rates_info": (
            "📜 *సేవా రేట్ల వివరాలు [నిదర్శన సమాచారం - అధికారికం కాదు]*\n"
            "(కేవలం పైలట్ ప్రదర్శన కొరకు మాత్రమే):\n\n"
            "🚤 *పడవ ప్రయాణం [నిదర్శన రేటు]*:\n"
            "• సాధారణ ఫెర్రీ: ₹50 ఒక్కొక్కరికి (లైఫ్ జాకెట్ తప్పనిసరి)\n"
            "• హావ్లాక్ బ్రిడ్జ్ ప్రత్యేక రైడ్ (30 నిమిషాలు): ₹150\n\n"
            "🛺 *ఆటో రిక్షా నిర్ణీత చార్జీలు [నిదర్శన రేటు]*:\n"
            "• రాజమండ్రి స్టేషన్ నుండి పుష్కర ఘాట్: ₹60 స్థిర చార్జీ\n"
            "• కోటిలింగాల ఘాట్ నుండి సెంట్రల్ బస్ స్టాండ్: ₹80\n\n"
            "🧳 *క్లాక్‌రూమ్ బ్యాగ్ భద్రత [నిదర్శన రేటు]*: 12 గంటలకు ₹20 ప్రతి బ్యాగ్‌కు\n\n"
            "⚠️ ఎవరైనా అధిక చార్జీలు డిమాండ్ చేస్తే వెంటనే *7* అని రిప్లై ఇచ్చి ఫిర్యాదు చేయండి!"
        ),
        "scam_ask_category": (
            "⚖️ *అదనపు చార్జీలు / మోసాల పై ఫిర్యాదు*\n"
            "ఏ సేవలో అధిక చార్జీలు వసూలు చేస్తున్నారు?\n"
            "1. పడవలు / బోట్ ప్రయాణం\n"
            "2. ఆటో లేదా టాక్సీ\n"
            "3. క్లాక్‌రూమ్\n"
            "4. పూజా సామగ్రి / పురోహితులు\n"
            "5. లాడ్జింగ్ / ఆహారం\n\n"
            "_1 నుండి 5 వరకు నంబర్ పంపండి._"
        ),
        "scam_ask_details": "దయచేసి వివరాలు పంపండి: వాహనం/స్టాల్ నంబర్, డిమాండ్ చేసిన మొత్తం, అధికారిక రేటు మరియు లొకేషన్:",
        "scam_report_created": (
            "✅ *ఫిర్యాదు నమోదైంది: {report_no}*\n"
            "ఈ సమాచారం రాజమండ్రి స్పెషల్ ఎన్‌ఫోర్స్‌మెంట్ స్క్వాడ్ (ఫ్లైయింగ్ స్క్వాడ్)కు చేరవేయబడింది. తనిఖీలు చేపట్టబడతాయి."
        ),
        "helpdesk_info": (
            "📞 *పుష్కరాలు హెల్ప్‌లైన్లు & అత్యవసర నంబర్లు*:\n\n"
            "🚨 *పుష్కర హెల్ప్‌లైన్*: 1800-425-2027 [నిదర్శన సమాచారం - అధికారికం కాదు]\n"
            "👮 *పోలీస్ మరియు అత్యవసర సేవలు*: 112 [రియల్ అత్యవసర నంబర్]\n"
            "🚑 *వైద్య అత్యవసర సేవలు (అంబులెన్స్)*: 108 / 104 [రియల్ అత్యవసర నంబర్]\n\n"
            "కోటిలింగాల మరియు పుష్కర ఘాట్ల వద్ద 'బంధం క్యూఆర్' సహాయ కేంద్రాలు ఏర్పాటు చేయబడ్డాయి."
        ),
        "fallback": "క్షమించండి, మీ సందేశం అర్థం కాలేదు. ప్రధాన మెనూ కోసం *0* అని టైప్ చేయండి లేదా 1 నుండి 9 వరకు ఎంచుకోండి."
    },
    "hi": {
        "welcome": (
            "🙏 *गोदावरी पुष्करालु 2027 'बंधम' सहायक में आपका स्वागत है!*\n\n"
            "[पायलट प्रोटोटाइप - नमूना डेटा / PILOT PROTOTYPE - SAMPLE DATA]\n"
            "राजमंड्री और कोव्वूर घाटों पर श्रद्धालुओं की सहायता हेतु पायलट सहायक।\n\n"
            "कृपया एक विकल्प चुनें (संख्या या पाठ भेजें):\n"
            "1️⃣ *बंधम क्यूआर (Bandham QR) परिवार पंजीकरण*\n"
            "2️⃣ *खोए हुए बच्चे / परिजन की आपातकालीन रिपोर्ट*\n"
            "3️⃣ *मुझे एक खोया हुआ बच्चा मिला है*\n"
            "4️⃣ *प्रमुख स्नान घाट व जन सुविधाएं*\n"
            "5️⃣ *शौचालय व स्वच्छता शिकायत*\n"
            "6️⃣ *सेवा दरें [नमूना डेटा - आधिकारिक नहीं]*\n"
            "7️⃣ *अधिक वसूली / धोखाधड़ी की शिकायत*\n"
            "8️⃣ *आपातकालीन हेल्पडेस्क व पुलिस सहायता*\n"
            "9️⃣ *भाषा बदलें / Change Language / భాష మార్చండి*\n\n"
            "_सुझाव: आप 'पुष्कर घाट कहाँ है' या 'खोया बच्चा' सीधे लिख भी सकते हैं।_"
        ),
        "menu_hint": "\n\n_मुख्य मेनू के लिए कभी भी *0* या *MENU* भेजें।_",
        "lang_selection": (
            "🌐 *भाषा चुनें / Select Language / భాషను ఎంచుకోండి:*\n\n"
            "1. తెలుగు (Telugu)\n"
            "2. English\n"
            "3. हिन्दी (Hindi)\n\n"
            "_1, 2 अथवा 3 लिखकर भेजें।_"
        ),
        "lang_updated": "आपकी भाषा हिन्दी में बदल दी गई है।",
        "reg_intro": (
            "🛡️ *बंधम क्यूआर परिवार सुरक्षा पंजीकरण*\n\n"
            "बंधम रिस्टबैंड आपके परिवार को आपातकालीन सुरक्षा ग्रिड से जोड़ता है। "
            "भीड़ में बिछड़ने पर अधिकृत हेल्पडेस्क आपका मोबाइल नंबर सार्वजनिक किए बिना तुरंत आपसे संपर्क करेगा।\n\n"
            "🔒 *सहमति*: हम केवल नाम, संपर्क सूत्र व आश्रितों की संख्या दर्ज करते हैं।\n\n"
            "क्या आप पंजीकरण जारी रखना चाहते हैं?\n"
            "जारी रखने के लिए *YES* भेजें, अथवा रद्द करने के लिए *0* भेजें।"
        ),
        "reg_ask_guardian_name": "कृपया *अभिभावक / परिवार के मुखिया का पूरा नाम* दर्ज करें (कम से कम 3 अक्षर):\n\n_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_",
        "invalid_guardian_name": "⚠️ *अमान्य नाम*: कृपया कम से कम 3 अक्षरों वाला मान्य नाम दर्ज करें (केवल संख्याएँ अथवा एकल अक्षर मान्य नहीं हैं):\n\n_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_",
        "reg_ask_backup_phone": "कृपया एक *वैकल्पिक संपर्क नंबर* दर्ज करें (10 अंकों का मोबाइल नंबर अथवा *SKIP* लिखें):\n\n_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_",
        "invalid_backup_phone": "⚠️ *अमान्य वैकल्पिक फ़ोन*: कृपया 10 अंकों का मान्य भारतीय मोबाइल नंबर (6-9 से प्रारंभ) दर्ज करें अथवा *SKIP* लिखें:\n\n_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_",
        "reg_ask_bands_count": "परिवार के लिए कितने बंधम रिस्टबैंड चाहिए? (1 से 6 तक संख्या लिखें):\n\n_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_",
        "invalid_bands_count": "⚠️ *अमान्य रिस्टबैंड संख्या*: कृपया 1 से 6 के बीच की संख्या दर्ज करें (अधिकतम 6 रिस्टबैंड):\n\n_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_",
        "photo_guidance": (
            "📸 *फोटो / सेल्फी जानकारी*:\n"
            "व्हाट्सएप पर फोटो भेजने की आवश्यकता नहीं है। घाट पर बंधम स्टॉल पर हमारे ऑपरेटर फोटो सीधे सिस्टम में दर्ज कर सकते हैं।\n\n"
            "अभी के लिए कृपया परिवार के सदस्यों के नाम लिखें, या स्टॉल पर विवरण देने के लिए *SKIP* (या *0*) टाइप करें।\n\n"
            "_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_"
        ),
        "reg_ask_members": (
            "कृपया परिवार के सदस्यों के *नाम और कपड़ों का विवरण* दर्ज करें (उदा. 'आरव, उम्र 7, पीली कमीज'):\n"
            "_अथवा यह विवरण सीधे घाट के स्टॉल पर देने के लिए *SKIP* टाइप करें।_\n\n"
            "_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_"
        ),
        "invalid_members_details": (
            "⚠️ *सदस्य विवरण*:\n"
            "कृपया सदस्यों के नाम लिखें (उदा. 'आरव, उम्र 7, पीली कमीज'), अथवा यह विवरण स्टॉल पर देने के लिए *SKIP* टाइप करें।\n\n"
            "_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_"
        ),
        "reg_success": (
            "✅ *पंजीकरण सफलतापूर्वक दर्ज हुआ!*\n\n"
            "📋 *पंजीकरण संदर्भ*: *{ref}*\n"
            "👤 *अभिभावक*: {name}\n"
            "📞 *फ़ोन*: {phone}\n"
            "🏷️ *रिस्टबैंड संख्या*: {count}\n\n"
            "⚠️ *महत्वपूर्ण अगला कदम*: रिस्टबैंड अभी सक्रिय नहीं हैं। कृपया कोटिलिंगला या पुष्कर घाट पर स्थित *बंधम क्यूआर स्टॉल* पर जाकर संदर्भ *{ref}* दिखाएं। सत्यापन के पश्चात आपको वाटरप्रूफ रिस्टबैंड व गुप्त 6-अंकों का *रिलीज़ पिन (PIN)* प्रदान किया जाएगा।"
        ),
        "missing_child_intro": (
            "🚨 *आपातकाल: लापता बच्चे की रिपोर्ट*\n\n"
            "यदि आप घाट पर हैं तो कृपया शांत रहें और तुरंत नजदीकी *पुलिस हेल्पडेस्क* पर पहुंचें।\n\n"
            "क्या लापता व्यक्ति के पास बंधम रिस्टबैंड है?\n"
            "1. हाँ, मेरे पास बैंड आईडी या संदर्भ संख्या है\n"
            "2. नहीं / बैंड आईडी नहीं है\n\n"
            "_1 या 2 लिखकर भेजें।_"
        ),
        "missing_ask_band_id": "कृपया *बैंड आईडी* (BND-XXXXXXXX) या पंजीकरण संदर्भ दर्ज करें:",
        "missing_ask_details": (
            "कृपया बच्चे का *नाम, अनुमानित उम्र, कपड़ों का रंग/प्रकार* और *अंतिम बार देखे जाने का स्थान* दर्ज करें (उदा. 'साईं, उम्र 7, पीली कमीज, पुष्कर घाट पिलर 12'):\n\n"
            "_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_"
        ),
        "invalid_missing_details": (
            "⚠️ *अधिक विवरण आवश्यक*:\n"
            "लाखों की भीड़ में केवल एक नाम से बच्चे को खोजना संभव नहीं है।\n"
            "कृपया बच्चे की उम्र, कपड़ों का रंग/प्रकार और अंतिम बार देखे जाने का स्थान लिखें:\n\n"
            "_उदाहरण: 'साईं, उम्र 7, पीली कमीज, पुष्कर घाट'_\n\n"
            "_(रद्द करने के लिए *0* अथवा *MENU* लिखें)_"
        ),
        "missing_case_created": (
            "🚨 *आपातकालीन अलर्ट दर्ज हुआ*\n\n"
            "केस संख्या: *{case_no}*\n"
            "विवरण: {details}\n"
            "स्थिति: *समस्त हेल्पडेस्क कर्मियों व पुलिस को BOLO अलर्ट प्रसारित*\n\n"
            "📢 लाउडस्पीकर प्रसारण हेतु तेलुगु उद्घोषणा तैयार की गई है। तुरंत नजदीकी पुलिस सहायता केंद्र पर संपर्क करें।"
        ),
        "case_followup_hint": (
            "ℹ️ *केस {case_no} सक्रिय है*।\n"
            "आप अतिरिक्त विवरण (जैसे 'नीली चप्पल पहनी है') लिख सकते हैं, अथवा 'कैसे खोजेंगे' या 'कहाँ जाना है' पूछ सकते हैं।\n\n"
            "_(मुख्य मेनू के लिए *0* लिखें)_"
        ),
        "how_search_works": (
            "ℹ️ *पुष्करालु में लापता व्यक्ति की खोज कैसे होती है?*:\n\n"
            "1. 📢 *लाउडस्पीकर घोषणा*: रिपोर्ट दर्ज होते ही घाटों के 40+ लाउडस्पीकरों पर घोषणा शुरू की जाती है।\n"
            "2. 🏃 *200+ ग्राउंड रनर*: विवरण तुरंत ड्यूटी पर तैनात पुलिसकर्मियों व स्वयंसेवकों के फोन पर प्रसारित होता है।\n"
            "3. 👮 *पुलिस कंट्रोल पोस्ट*: घाट के निकास द्वारों व रेलवे/बस स्टेशनों पर अलर्ट जारी होता है।\n\n"
            "📍 *तत्काल कार्रवाई*: कृपया तुरंत नजदीकी *पुलिस सहायता केंद्र* पर जाएं और बच्चे की फोटो दिखाएं।\n\n"
            "_अतिरिक्त विवरण के लिए यहाँ लिखें अथवा मेनू के लिए *0* भेजें।_"
        ),
        "next_steps_instructions": (
            "📍 *परिजनों के लिए आवश्यक कदम*:\n\n"
            "1. तुरंत निकटतम *पुलिस कंट्रोल बूथ* पर जाएं।\n"
            "2. अपना फोन चालू रखें (कॉल आ सकती है)।\n"
            "3. फोन में उपलब्ध बच्चे की तस्वीर पुलिस को दिखाएं।\n\n"
            "_मुख्य मेनू के लिए *0* भेजें।_"
        ),
        "case_updated": "✅ *केस {case_no} अपडेट हुआ*: अतिरिक्त विवरण '{update}' दर्ज कर ग्राउंड टीमों को भेज दिया गया है।\n\n_(मेनू के लिए *0* भेजें)_",
        "case_active_reminder": "🚨 *केस {case_no} सक्रिय है*। कृपया तुरंत पुलिस हेल्पडेस्क पर जाएं। अतिरिक्त विवरण यहाँ लिख सकते हैं अथवा *0* भेजें।",
        "found_child_intro": (
            "⚠️ *बाल सुरक्षा निर्देश*\n\n"
            "सहायता के लिए धन्यवाद। *महत्वपूर्ण सुरक्षा नियम*:\n"
            "1. बच्चे को किसी भी अनजान व्यक्ति को न सौंपें।\n"
            "2. यदि बच्चे के पास रिस्टबैंड है तो उस पर मुद्रित बैंड आईडी देखें।\n\n"
            "क्या बच्चे के पास रिस्टबैंड है?\n"
            "*बैंड आईडी* (जैसे BND-XXXXXX) भेजें अथवा *NO* लिखें।"
        ),
        "found_ask_location": (
            "आप बच्चे के साथ वर्तमान में कहाँ हैं?\n"
            "1. कोटिलिंगला घाट (हेल्पडेस्क 1)\n"
            "2. पुष्कर घाट (हेल्पडेस्क 2)\n"
            "3. सरस्वती घाट\n"
            "4. मार्कंडेय घाट\n"
            "5. कोव्वूर गोष्पाद क्षेत्रम घाट\n"
            "6. अन्य स्थान\n\n"
            "_1 से 5 चुनें अथवा स्थान का नाम लिखें।_"
        ),
        "found_child_reported": (
            "✅ *रिपोर्ट दर्ज की गई*\n\n"
            "केस संख्या: *{case_no}*\n"
            "स्थान: {location}\n\n"
            "नजदीकी बचाव दल भेजा जा रहा है। कृपया बच्चे को लेकर निकटतम पुलिसकर्मी या बंधम बूथ पर जाएं।"
        ),
        "ghats_info": (
            "🌊 *गोदावरी पुष्करालु 2027 प्रमुख घाट [नमूना डेटा]*:\n\n"
            "1. *कोटिलिंगला घाट (राजमंड्री)*: 3 किमी लंबा, 24 घंटे मेडिकल कैंप, 6 सहायता केंद्र।\n"
            "2. *पुष्कर घाट*: मुख्य स्नान घाट, रेलवे स्टेशन से 1.2 किमी।\n"
            "3. *सरस्वती घाट*: कम भीड़भाड़, बुजुर्गों के लिए विशेष रैंप।\n"
            "4. *गोष्पाद क्षेत्रम घाट (कोव्वूर)*: पश्चिम गोदावरी तट, विशेष बस स्टैंड।"
        ),
        "sanitation_intro": (
            "🧹 *स्वच्छता रिपोर्ट व समाधान*\n\n"
            "1. गंदा शौचालय\n"
            "2. पानी की कमी\n"
            "3. कचरा जमाव\n"
            "4. सुविधा क्यूआर स्कैन\n\n"
            "_1, 2, 3 या 4 चुनें।_"
        ),
        "sanitation_ask_location": "कृपया घाट व शौचालय ब्लॉक का नाम बताएं (जैसे पुष्कर घाट ब्लॉक 2):",
        "sanitation_ticket_created": (
            "✅ *स्वच्छता शिकायत दर्ज: {ticket_no}*\n"
            "स्थान: {facility}\n\n"
            "सफाई टीम रवाना कर दी गई है। सफाई उपरांत फोटो सत्यापन के बाद ही टिकट बंद होगा।"
        ),
        "rates_info": (
            "📜 *सेवा दरें [नमूना डेटा - आधिकारिक नहीं]*\n"
            "(केवल पायलट प्रदर्शन हेतु नमूना दरें):\n\n"
            "🚤 *नाव यात्रा [नमूना]*: साधारण नौका ₹50 प्रति व्यक्ति (लाइफ जैकेट अनिवार्य)\n"
            "🛺 *ऑटो रिक्शा [नमूना]*: रेलवे स्टेशन से पुष्कर घाट ₹60 निर्धारित\n"
            "🧳 *क्लॉक रूम [नमूना]*: ₹20 प्रति बैग (12 घंटे)\n\n"
            "⚠️ अधिक पैसे मांगने पर तुरंत *7* दबाकर शिकायत दर्ज करें।"
        ),
        "scam_ask_category": "अधिक वसूली किस सेवा में हुई? (1. नाव 2. ऑटो 3. क्लॉक रूम 4. पूजा 5. अन्य):",
        "scam_ask_details": "कृपया वाहन/स्टॉल नंबर, वसूली गई राशि व स्थान का विवरण दें:",
        "scam_report_created": "✅ *शिकायत दर्ज: {report_no}*। स्पेशल एन्फोर्समेंट टीम को सूचित कर दिया गया है।",
        "helpdesk_info": (
            "📞 *हेल्पलाइन व आपातकालीन संपर्क*:\n\n"
            "🚨 *पुष्करालु हेल्पलाइन*: 1800-425-2027 [नमूना डेटा - आधिकारिक नहीं]\n"
            "👮 *पुलिस व बाल सुरक्षा*: 112 [वास्तविक आपातकालीन नंबर]\n"
            "🚑 *एम्बुलेंस*: 108 / 104 [वास्तविक आपातकालीन नंबर]"
        ),
        "fallback": "संदेश समझ नहीं आया। मुख्य मेनू के लिए *0* भेजें अथवा 1 से 9 में से चुनें।"
    }
}


def generate_telugu_pa_script(child_name: str, age: Optional[int], clothing: str, last_seen: str) -> str:
    """
    Generates an official Telugu Public Address announcement script for ghat PA systems.
    """
    age_str = f"సుమారు {age} సంవత్సరాల వయస్సు గల" if age else ""
    return (
        f"అత్యవసర ప్రకటన: దయచేసి భక్తులు గమనించగలరు. {last_seen} వద్ద {age_str} "
        f"'{child_name}' అనే పేరు గల బాలుడు/బాలిక తప్పిపోయారు. "
        f"ఆచూకీ తెలిసిన వారు సమీపంలోని బంధం హెల్ప్‌డెస్క్ లేదా పోలీస్ కంట్రోల్ రూమ్‌కు సమాచారం ఇవ్వగలరు. "
        f"దుస్తుల వివరాలు: {clothing}."
    )


class ConversationEngine:
    """
    Central conversation state machine supporting session timeout,
    natural language intent recognition, and multi-turn flows in Telugu, English, and Hindi.
    """

    @staticmethod
    async def get_or_create_session(db: AsyncSession, phone_number: str) -> ConversationSession:
        result = await db.execute(
            select(ConversationSession).where(ConversationSession.phone_number == phone_number)
        )
        session = result.scalar_one_or_none()
        if not session:
            session = ConversationSession(
                phone_number=phone_number,
                language="te",  # Default to Telugu for Godavari Pushkaralu
                current_state="MAIN_MENU",
                context_data_json="{}",
                last_interaction_at=datetime.now(timezone.utc)
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        return session

    @classmethod
    async def process_incoming_message(
        cls,
        db: AsyncSession,
        phone_number: str,
        message_text: str,
        button_payload: Optional[str] = None
    ) -> Tuple[List[str], str, str]:
        session = await cls.get_or_create_session(db, phone_number)
        lang = session.language or "te"
        context = json.loads(session.context_data_json or "{}")
        text = (button_payload or message_text).strip()
        text_lower = text.lower()

        # Universal resets, cancels, and greetings
        greetings = [
            "0", "menu", "main menu", "మెనూ", "మేనూ", "मेनू", "reset", "start",
            "hi", "hello", "hey", "నమస్కారం", "నమస్తే", "హలో", "హాయ్",
            "नमस्ते", "प्रणाम", "ram ram", "pushkaralu", "bandham",
            "cancel", "రద్దు", "ఆపండి", "stop", "quit", "exit", "back", "వెనక్కి"
        ]
        if text_lower in greetings or any(text_lower.startswith(g) for g in ["hi", "hello", "hey", "నమస్కారం", "నమస్తే", "नमस्ते"]):
            session.current_state = "MAIN_MENU"
            session.context_data_json = "{}"
            await db.commit()
            return [TEXTS[lang]["welcome"]], lang, "MAIN_MENU"

        # Universal Language Switcher keywords
        if text_lower in ["9", "language", "change language", "భాష", "భాష మార్చండి", "भाषा"]:
            session.current_state = "AWAITING_LANG"
            await db.commit()
            return [TEXTS[lang]["lang_selection"]], lang, "AWAITING_LANG"

        # State: Language selection
        if session.current_state == "AWAITING_LANG":
            if text in ["1", "తెలుగు", "telugu"]:
                session.language = "te"
                lang = "te"
            elif text in ["2", "english", "en"]:
                session.language = "en"
                lang = "en"
            elif text in ["3", "हिन्दी", "hindi", "hi"]:
                session.language = "hi"
                lang = "hi"
            else:
                return [TEXTS[lang]["lang_selection"]], lang, "AWAITING_LANG"

            session.current_state = "MAIN_MENU"
            session.context_data_json = "{}"
            await db.commit()
            return [TEXTS[lang]["lang_updated"], TEXTS[lang]["welcome"]], lang, "MAIN_MENU"

        # Natural Language Fallthrough from MAIN_MENU
        if session.current_state == "MAIN_MENU":
            # Quick Natural Language Keyword Matching
            if any(k in text_lower for k in ["missing", "lost child", "పాప తప్పిపోయింది", "బాబు తప్పిపోయాడు", "పిల్లవాడు తప్పిపోయాడు", "తప్పిపోయారు", "खो गया", "लापता"]):
                text = "2"
            elif any(k in text_lower for k in ["found child", "found kid", "దొరికాడు", "దొరికింది", "పిల్లవాడు దొరికాడు", "बच्चा मिला"]):
                text = "3"
            elif any(k in text_lower for k in ["ghat", "ghats", "pushkar ghat", "kotilingala", "ఘాట్", "పుష్కర ఘాట్", "కోటిలింగాల", "घाट"]):
                text = "4"
            elif any(k in text_lower for k in ["toilet", "bathroom", "washroom", "clean", "garbage", "మరుగుదొడ్డి", "చెత్త", "పారిశుధ్యం", "शौचालय", "सफाई"]):
                text = "5"
            elif any(k in text_lower for k in ["rate", "rates", "fare", "price", "boat rate", "auto fare", "ధరలు", "రేట్లు", "చార్జీలు", "किराया", "दरें"]):
                text = "6"
            elif any(k in text_lower for k in ["scam", "overcharge", "cheating", "దోపిడీ", "మోసం", "లూటీ", "धोखा", "ज्यादा पैसे"]):
                text = "7"
            elif any(k in text_lower for k in ["police", "helpdesk", "emergency", "phone", "help", "పోలీస్", "హెల్ప్‌లైన్", "సహాయం", "मदद", "पुलिस"]):
                text = "8"
            elif any(k in text_lower for k in ["register", "bandham", "wristband", "band", "నమోదు", "రిజిస్ట్రేషన్", "బ్యాండ్", "पंजीकरण"]):
                text = "1"
            elif any(k in text_lower for k in [
                "how can you find", "how do you find", "how to find", "how search", "name only",
                "ఎలా వెతుకుతారు", "ఎలా కనిపెడతారు", "ఎలా వెదుకుతారు", "పేరుతో ఎలా", "కేవలం పేరుతో",
                "कैसे खोजेंगे", "कैसे ढूँढेंगे"
            ]):
                return [TEXTS[lang]["how_search_works"] + TEXTS[lang]["menu_hint"]], lang, "MAIN_MENU"

            # Main Menu Routing
            if text == "1":
                session.current_state = "REG_CONSENT"
                await db.commit()
                return [TEXTS[lang]["reg_intro"]], lang, "REG_CONSENT"

            elif text == "2":
                session.current_state = "MISSING_CHOICE"
                await db.commit()
                return [TEXTS[lang]["missing_child_intro"]], lang, "MISSING_CHOICE"

            elif text == "3":
                session.current_state = "FOUND_ASK_BAND"
                await db.commit()
                return [TEXTS[lang]["found_child_intro"]], lang, "FOUND_ASK_BAND"

            elif text == "4":
                return [TEXTS[lang]["ghats_info"] + TEXTS[lang]["menu_hint"]], lang, "MAIN_MENU"

            elif text == "5":
                session.current_state = "SANITATION_CHOICE"
                await db.commit()
                return [TEXTS[lang]["sanitation_intro"]], lang, "SANITATION_CHOICE"

            elif text == "6":
                return [TEXTS[lang]["rates_info"] + TEXTS[lang]["menu_hint"]], lang, "MAIN_MENU"

            elif text == "7":
                session.current_state = "SCAM_ASK_CATEGORY"
                await db.commit()
                return [TEXTS[lang]["scam_ask_category"]], lang, "SCAM_ASK_CATEGORY"

            elif text == "8":
                return [TEXTS[lang]["helpdesk_info"] + TEXTS[lang]["menu_hint"]], lang, "MAIN_MENU"

            else:
                # Check if this user has an open missing person case in the database
                active_case_res = await db.execute(
                    select(Case).where(
                        Case.reporter_contact == phone_number,
                        Case.case_type == "MISSING_CHILD",
                        Case.status == "OPEN"
                    ).order_by(Case.created_at.desc())
                )
                open_case = active_case_res.scalar_one_or_none()
                if open_case and len(text) >= 3 and not text.isdigit():
                    # 1. Check for search protocol question
                    if any(k in text_lower for k in [
                        "how can you find", "how do you find", "how to find", "how search", "name only",
                        "ఎలా వెతుకుతారు", "ఎలా కనిపెడతారు", "ఎలా వెదుకుతారు", "పేరుతో ఎలా", "కేవలం పేరుతో",
                        "कैसे खोजेंगे", "कैसे ढूँढेंगे"
                    ]):
                        context["active_case_no"] = open_case.case_number
                        session.current_state = "CASE_ACTIVE_FOLLOWUP"
                        session.context_data_json = json.dumps(context)
                        await db.commit()
                        return [TEXTS[lang]["how_search_works"]], lang, "CASE_ACTIVE_FOLLOWUP"

                    # 2. Check for next steps question
                    if any(k in text_lower for k in [
                        "what next", "what to do", "where to go", "where should i go", "police booth", "booth",
                        "తర్వాత ఏం చేయాలి", "నేను ఏం చేయాలి", "ఎక్కడికి వెళ్ళాలి", "పోలీస్ బూత్",
                        "आगे क्या करें", "कहाँ जाना है"
                    ]):
                        context["active_case_no"] = open_case.case_number
                        session.current_state = "CASE_ACTIVE_FOLLOWUP"
                        session.context_data_json = json.dumps(context)
                        await db.commit()
                        return [TEXTS[lang]["next_steps_instructions"]], lang, "CASE_ACTIVE_FOLLOWUP"

                    # 3. User is sending additional description/features/clothing for their open case
                    existing = json.loads(open_case.bolo_details_json or "{}")
                    prior_desc = existing.get("description", "")
                    new_desc = f"{prior_desc}; Update: {text}"
                    existing["description"] = new_desc
                    open_case.bolo_details_json = json.dumps(existing)
                    context["active_case_no"] = open_case.case_number
                    session.current_state = "CASE_ACTIVE_FOLLOWUP"
                    session.context_data_json = json.dumps(context)
                    await db.commit()
                    return [
                        TEXTS[lang]["case_updated"].format(case_no=open_case.case_number, update=text)
                    ], lang, "CASE_ACTIVE_FOLLOWUP"

                return [TEXTS[lang]["fallback"]], lang, "MAIN_MENU"

        # --- FLOW 1: FAMILY REGISTRATION STATE MACHINE ---
        if session.current_state == "REG_CONSENT":
            if any(k in text_lower for k in ["yes", "y", "సరే", "అవును", "हाँ", "ha", "ok"]):
                session.current_state = "REG_NAME"
                await db.commit()
                return [TEXTS[lang]["reg_ask_guardian_name"]], lang, "REG_NAME"
            else:
                session.current_state = "MAIN_MENU"
                await db.commit()
                return [TEXTS[lang]["welcome"]], lang, "MAIN_MENU"

        if session.current_state == "REG_NAME":
            if not is_valid_guardian_name(text):
                return [TEXTS[lang]["invalid_guardian_name"]], lang, "REG_NAME"
            context["guardian_name"] = text.strip()
            session.current_state = "REG_BACKUP_PHONE"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["reg_ask_backup_phone"]], lang, "REG_BACKUP_PHONE"

        if session.current_state == "REG_BACKUP_PHONE":
            is_valid, is_skip, sanitized_phone = is_valid_backup_phone(text)
            if not is_valid:
                return [TEXTS[lang]["invalid_backup_phone"]], lang, "REG_BACKUP_PHONE"
            context["backup_phone"] = sanitized_phone if not is_skip else ""
            session.current_state = "REG_BANDS_COUNT"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["reg_ask_bands_count"]], lang, "REG_BANDS_COUNT"

        if session.current_state == "REG_BANDS_COUNT":
            is_valid, count_val = is_valid_band_count(text)
            if not is_valid:
                return [TEXTS[lang]["invalid_bands_count"]], lang, "REG_BANDS_COUNT"
            context["bands_count"] = count_val
            session.current_state = "REG_MEMBERS"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["reg_ask_members"]], lang, "REG_MEMBERS"

        if session.current_state == "REG_MEMBERS":
            is_valid, is_skip, is_photo = is_valid_member_visual_details(text)
            if is_photo:
                return [TEXTS[lang]["photo_guidance"]], lang, "REG_MEMBERS"

            if not is_valid:
                return [TEXTS[lang]["invalid_members_details"]], lang, "REG_MEMBERS"

            if is_skip:
                members_desc = "To be recorded in-person at Bandham stall during band issuance."
            else:
                members_desc = text.strip()

            context["members_desc"] = members_desc
            # Generate pending cluster in database
            cluster_code = f"FAM-{secrets.token_hex(3).upper()}"
            reg_ref = f"REG-{secrets.randbelow(900000) + 100000}"

            new_cluster = FamilyCluster(
                cluster_code=cluster_code,
                registration_ref=reg_ref,
                primary_guardian_name=context.get("guardian_name", "Pilgrim Guardian"),
                primary_phone=phone_number,
                backup_phone=context.get("backup_phone"),
                whatsapp_phone=phone_number,
                consent_given=True,
                status="PENDING_VERIFICATION",
                members_count=context.get("bands_count", 2),
                members_json=json.dumps([{"notes": members_desc}]),
                notes="Created via WhatsApp Assistant"
            )
            db.add(new_cluster)
            await db.commit()

            msg = TEXTS[lang]["reg_success"].format(
                ref=reg_ref,
                name=context.get("guardian_name"),
                phone=phone_number,
                count=context.get("bands_count", 2)
            ) + TEXTS[lang]["menu_hint"]

            session.current_state = "MAIN_MENU"
            session.context_data_json = "{}"
            await db.commit()
            return [msg], lang, "MAIN_MENU"

        # --- FLOW 2: REPORT MISSING CHILD ---
        if session.current_state == "MISSING_CHOICE":
            if text in ["1", "yes"]:
                session.current_state = "MISSING_ASK_BAND_ID"
                await db.commit()
                return [TEXTS[lang]["missing_ask_band_id"]], lang, "MISSING_ASK_BAND_ID"
            else:
                session.current_state = "MISSING_ASK_DETAILS"
                await db.commit()
                return [TEXTS[lang]["missing_ask_details"]], lang, "MISSING_ASK_DETAILS"

        if session.current_state == "MISSING_ASK_BAND_ID":
            context["missing_band_id"] = text.upper()
            session.current_state = "MISSING_ASK_DETAILS"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["missing_ask_details"]], lang, "MISSING_ASK_DETAILS"

        if session.current_state == "MISSING_ASK_DETAILS":
            if not is_valid_missing_details(text):
                return [TEXTS[lang]["invalid_missing_details"]], lang, "MISSING_ASK_DETAILS"

            case_no = f"CASE-2027-{secrets.randbelow(9000) + 1000}"
            band_id = context.get("missing_band_id")
            
            # Find associated cluster if band exists
            cluster_id = None
            if band_id:
                band_res = await db.execute(select(Band).where(Band.band_id == band_id))
                band_obj = band_res.scalar_one_or_none()
                if band_obj:
                    cluster_id = band_obj.cluster_id

            # Generate Telugu PA announcement script
            pa_script = generate_telugu_pa_script(
                child_name="Missing Person",
                age=None,
                clothing=text,
                last_seen="Godavari Pushkar Ghat"
            )

            new_case = Case(
                case_number=case_no,
                case_type="MISSING_CHILD",
                band_id=band_id,
                cluster_id=cluster_id,
                reported_by_name="Guardian via WhatsApp",
                reporter_contact=phone_number,
                reporter_role="GUARDIAN",
                location_name="Reported via WhatsApp Assistant",
                status="OPEN",
                bolo_details_json=json.dumps({"description": text}),
                telugu_announcement_script=pa_script
            )
            db.add(new_case)
            await db.commit()

            msg = TEXTS[lang]["missing_case_created"].format(
                case_no=case_no,
                details=text
            )
            followup = TEXTS[lang]["case_followup_hint"].format(case_no=case_no)

            context["active_case_no"] = case_no
            session.current_state = "CASE_ACTIVE_FOLLOWUP"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [msg, followup], lang, "CASE_ACTIVE_FOLLOWUP"

        # --- STATE: CASE ACTIVE FOLLOW-UP (Context preservation after reporting a missing person) ---
        if session.current_state == "CASE_ACTIVE_FOLLOWUP":
            active_case_no = context.get("active_case_no")
            # 1. User asks how search works or how name-only search works
            if any(k in text_lower for k in [
                "how can you find", "how do you find", "how to find", "how search", "name only",
                "ఎలా వెతుకుతారు", "ఎలా కనిపెడతారు", "ఎలా వెదుకుతారు", "పేరుతో ఎలా", "కేవలం పేరుతో",
                "कैसे खोजेंगे", "कैसे ढूँढेंगे"
            ]):
                return [TEXTS[lang]["how_search_works"]], lang, "CASE_ACTIVE_FOLLOWUP"

            # 2. User asks what to do next or where to go
            if any(k in text_lower for k in [
                "what next", "what to do", "where to go", "where should i go", "police booth", "booth",
                "తర్వాత ఏం చేయాలి", "నేను ఏం చేయాలి", "ఎక్కడికి వెళ్ళాలి", "పోలీస్ బూత్",
                "आगे क्या करें", "कहाँ जाना है"
            ]):
                return [TEXTS[lang]["next_steps_instructions"]], lang, "CASE_ACTIVE_FOLLOWUP"

            # 3. User provides additional descriptive details to append to the case
            if active_case_no and len(text) >= 3 and not text.isdigit():
                case_res = await db.execute(select(Case).where(Case.case_number == active_case_no))
                case_obj = case_res.scalar_one_or_none()
                if case_obj:
                    existing = json.loads(case_obj.bolo_details_json or "{}")
                    prior_desc = existing.get("description", "")
                    new_desc = f"{prior_desc}; Update: {text}"
                    existing["description"] = new_desc
                    case_obj.bolo_details_json = json.dumps(existing)
                    await db.commit()
                    return [
                        TEXTS[lang]["case_updated"].format(case_no=active_case_no, update=text)
                    ], lang, "CASE_ACTIVE_FOLLOWUP"

            return [
                TEXTS[lang]["case_active_reminder"].format(case_no=active_case_no)
            ], lang, "CASE_ACTIVE_FOLLOWUP"

        # --- FLOW 3: FOUND LOST CHILD ---
        if session.current_state == "FOUND_ASK_BAND":
            clean_band = text.upper().strip()
            if clean_band not in ["NO", "LEDU", "NAHI", "0"]:
                context["found_band_id"] = clean_band
            session.current_state = "FOUND_ASK_LOCATION"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["found_ask_location"]], lang, "FOUND_ASK_LOCATION"

        if session.current_state == "FOUND_ASK_LOCATION":
            loc_map = {
                "1": "Kotilingala Ghat (Helpdesk Booth 1)",
                "2": "Pushkar Ghat (Helpdesk Booth 2)",
                "3": "Saraswati Ghat",
                "4": "Markandeya Ghat",
                "5": "Kovvur Goshpada Kshetram Ghat"
            }
            location_str = loc_map.get(text, text)
            case_no = f"CASE-2027-{secrets.randbelow(9000) + 1000}"
            found_band = context.get("found_band_id")

            cluster_id = None
            if found_band:
                band_res = await db.execute(select(Band).where(Band.band_id == found_band))
                band_obj = band_res.scalar_one_or_none()
                if band_obj:
                    cluster_id = band_obj.cluster_id

            new_case = Case(
                case_number=case_no,
                case_type="FOUND_CHILD",
                band_id=found_band,
                cluster_id=cluster_id,
                reported_by_name="Helpful Pilgrim via WhatsApp",
                reporter_contact=phone_number,
                reporter_role="FINDER",
                location_name=location_str,
                status="OPEN"
            )
            db.add(new_case)
            await db.commit()

            # Attempt guardian alert if cluster found
            if cluster_id:
                cluster_res = await db.execute(select(FamilyCluster).where(FamilyCluster.id == cluster_id))
                cluster_obj = cluster_res.scalar_one_or_none()
                if cluster_obj:
                    notif = NotificationAttempt(
                        case_id=new_case.id,
                        cluster_id=cluster_id,
                        recipient_phone=cluster_obj.primary_phone,
                        channel="WHATSAPP",
                        status="INITIATED",
                        message_content=f"URGENT: Your family member with band {found_band} has been found at {location_str}."
                    )
                    db.add(notif)
                    await db.commit()

            msg = TEXTS[lang]["found_child_reported"].format(
                case_no=case_no,
                location=location_str
            ) + TEXTS[lang]["menu_hint"]

            session.current_state = "MAIN_MENU"
            session.context_data_json = "{}"
            await db.commit()
            return [msg], lang, "MAIN_MENU"

        # --- FLOW 5: SANITATION DISPATCH ---
        if session.current_state == "SANITATION_CHOICE":
            types = {
                "1": ("OVERFLOW", "Pushkar Ghat Toilets"),
                "2": ("NO_WATER", "Kotilingala Block 2"),
                "3": ("GARBAGE", "Markandeya Ghat Bins"),
                "4": ("FACILITY_QR", "Scanned Facility")
            }
            context["sanitation_type"] = types.get(text, ("UNHYGIENIC", "General Area"))[0]
            session.current_state = "SANITATION_ASK_LOC"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["sanitation_ask_location"]], lang, "SANITATION_ASK_LOC"

        if session.current_state == "SANITATION_ASK_LOC":
            ticket_no = f"SAN-2027-{secrets.randbelow(9000) + 1000}"
            new_ticket = SanitationTicket(
                ticket_number=ticket_no,
                facility_id=f"FAC-{secrets.token_hex(2).upper()}",
                facility_name=text,
                ghat_name=text,
                issue_type=context.get("sanitation_type", "UNHYGIENIC"),
                priority="HIGH",
                status="REPORTED",
                reported_via="WHATSAPP",
                reporter_phone=phone_number,
                description=f"Issue reported via WhatsApp: {text}"
            )
            db.add(new_ticket)
            await db.commit()

            msg = TEXTS[lang]["sanitation_ticket_created"].format(
                ticket_no=ticket_no,
                facility=text
            ) + TEXTS[lang]["menu_hint"]

            session.current_state = "MAIN_MENU"
            session.context_data_json = "{}"
            await db.commit()
            return [msg], lang, "MAIN_MENU"

        # --- FLOW 7: SCAM / OVERCHARGING REPORT ---
        if session.current_state == "SCAM_ASK_CATEGORY":
            cat_map = {
                "1": "BOAT_RIDE",
                "2": "AUTO_RICKSHAW",
                "3": "CLOAKROOM",
                "4": "PUJA_SERVICES",
                "5": "ACCOMMODATION"
            }
            context["scam_cat"] = cat_map.get(text, "GENERAL_SERVICE")
            session.current_state = "SCAM_ASK_DETAILS"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["scam_ask_details"]], lang, "SCAM_ASK_DETAILS"

        if session.current_state == "SCAM_ASK_DETAILS":
            report_no = f"SCAM-2027-{secrets.randbelow(9000) + 1000}"
            new_report = ScamReport(
                report_number=report_no,
                service_category=context.get("scam_cat", "GENERAL_SERVICE"),
                demanded_amount=150.0,
                official_amount=50.0,
                location="Rajahmundry Pushkaralu Zone",
                details=text,
                reporter_phone=phone_number,
                status="SUBMITTED"
            )
            db.add(new_report)
            await db.commit()

            msg = TEXTS[lang]["scam_report_created"].format(
                report_no=report_no
            ) + TEXTS[lang]["menu_hint"]

            session.current_state = "MAIN_MENU"
            session.context_data_json = "{}"
            await db.commit()
            return [msg], lang, "MAIN_MENU"

        # Fallback
        return [TEXTS[lang]["fallback"]], lang, "MAIN_MENU"
