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

TEXTS = {
    "en": {
        "welcome": (
            "🙏 *Welcome to Godavari Pushkaralu 2027 Bandham Assistant!*\n\n"
            "Official 24x7 Citizen Safety & Pilgrim Support for Rajahmundry & Kovvur.\n\n"
            "Please choose an option (reply with number or text):\n"
            "1️⃣ *Family Safety / Bandham QR Registration*\n"
            "2️⃣ *Report a Missing Child / Family Member*\n"
            "3️⃣ *I Found a Lost Child*\n"
            "4️⃣ *Find Ghats & Public Facilities*\n"
            "5️⃣ *Toilets & Sanitation Report*\n"
            "6️⃣ *Official Services & Approved Rates*\n"
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
        "reg_ask_guardian_name": "Please enter the *Primary Guardian's Full Name*:",
        "reg_ask_backup_phone": "Please enter an *Alternative / Backup Phone Number* (or reply *SKIP* if none):",
        "reg_ask_bands_count": "How many Bandham wristbands does your family need? (Enter a number from 1 to 6):",
        "reg_ask_members": (
            "Please provide the names and ages of the dependents (e.g., 'Aarav, age 7; Sita, age 70'):"
        ),
        "reg_success": (
            "✅ *Pending Registration Created Successfully!*\n\n"
            "📋 *Registration Reference*: *{ref}*\n"
            "👤 *Guardian*: {name}\n"
            "📞 *Primary Contact*: {phone}\n"
            "🏷️ *Wristbands Requested*: {count}\n\n"
            "⚠️ *Important Next Step*: Wristbands are *not yet active*. Please visit any authorized *Bandham QR Stall* at Kotilingala Ghat, Pushkar Ghat, or Kovvur Main Ghat with reference *{ref}*. Our staff will verify your contact, hand over physical tamper-evident bands, and issue your private *Handover Release PIN*."
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
            "Please provide details: Child's Name, Approximate Age, Clothing Color/Type, and Last Seen Location at the ghats:"
        ),
        "missing_case_created": (
            "🚨 *URGENT EMERGENCY ALERT ISSUED*\n\n"
            "Case Number: *{case_no}*\n"
            "Child Details: {details}\n"
            "Status: *ACTIVE BOLO DISPATCHED TO ALL HELPDESK RUNNERS & POLICE POSTS*\n\n"
            "📢 A public address announcement script has been generated for ghat operators.\n"
            "📍 *Immediate Action*: Please report to the nearest *Police Control Booth* or *Bandham Helpdesk #1 (Kotilingala Ghat)* immediately. Keep this WhatsApp chat open for updates."
        ),
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
            "🌊 *Godavari Pushkaralu 2027 Major Ghats & Facilities*:\n\n"
            "1. *Kotilingala Ghat (Rajahmundry)*: 3 km long, 24x7 medical camp, 6 helpdesk booths, 12 toilet blocks, lost child center.\n"
            "2. *Pushkar Ghat (Rajahmundry)*: Central holy dip point, Railway station 1.2 km away, mother-care feeding pods.\n"
            "3. *Saraswati Ghat*: Less crowded, elderly assistance ramps, specialized bathing enclosures.\n"
            "4. *Markandeya Ghat*: Near historic temple, dedicated transit parking feeder.\n"
            "5. *Goshpada Kshetram Ghat (Kovvur)*: West Godavari bank, special pilgrim bus terminal.\n\n"
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
            "📜 *Official Authority-Verified Rates (Pushkaralu 2027)*\n"
            "Approved by East Godavari District Collectorate & RTA:\n\n"
            "🚤 *Authorized Boat Rides*:\n"
            "• Standard Ghat Ferry: ₹50 / person (Life jacket mandatory)\n"
            "• Havelock Bridge Scenic Tour (30 mins): ₹150 / person\n\n"
            "🛺 *Auto-Rickshaw Pre-Fixed Tariffs*:\n"
            "• Rajahmundry Station to Pushkar Ghat: ₹60 flat\n"
            "• Kotilingala Ghat to Central Bus Stand: ₹80 flat\n\n"
            "🧳 *Official Cloakrooms*: ₹20 per bag for 12 hours\n"
            "🪔 *Temple Special Darshan*: Regulated official counter only.\n\n"
            "⚠️ If anyone demands higher rates, reply *7* immediately to report overcharging!"
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
            "📞 *Official Pushkaralu 24x7 Emergency Helpdesks*:\n\n"
            "🚨 *Central Emergency Toll-Free*: 1800-425-2027\n"
            "👮 *Police & Child Protection Cell*: 112 / 0883-2422027\n"
            "🚑 *Medical & Ambulance Control*: 108 / 104\n"
            "🌊 *River Safety & Water Police*: 0883-2422099\n\n"
            "Physical Helpdesk Stalls are located at every 200m along Kotilingala, Pushkar, and Kovvur Ghats. Look for yellow and blue 'BANDHAM QR' signboards."
        ),
        "fallback": "I didn't quite catch that. Reply *0* to see the main menu or choose an option (1-9)."
    },
    "te": {
        "welcome": (
            "🙏 *గోదావరి పుష్కరాలు 2027 బంధం అసిస్టెంట్‌కు స్వాగతం!*\n\n"
            "రాజమండ్రి మరియు కొవ్వూరు ఘాట్ల వద్ద భక్తుల రక్షణ, కుటుంబ భద్రత మరియు సహాయం కొరకు అధికారిక సేవ.\n\n"
            "దయచేసి కింది సేవలలో ఒకదాన్ని ఎంచుకోండి (నంబర్ లేదా టెక్స్ట్ పంపండి):\n"
            "1️⃣ *బంధం క్యూఆర్ (Bandham QR) కుటుంబ నమోదు*\n"
            "2️⃣ *తప్పిపోయిన పిల్లలు / కుటుంబ సభ్యుల అత్యవసర రిపోర్ట్*\n"
            "3️⃣ *తప్పిపోయిన పిల్లవాడు దొరికాడు*\n"
            "4️⃣ *స్నాన ఘాట్లు మరియు ముఖ్య సదుపాయాలు*\n"
            "5️⃣ *మరుగుదొడ్లు మరియు పారిశుధ్య సమస్యల ఫిర్యాదు*\n"
            "6️⃣ *అధికారిక సేవా చార్జీలు మరియు రేట్ల వివరాలు*\n"
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
        "reg_ask_guardian_name": "దయచేసి *కుటుంబ పెద్ద / సంరక్షకుడి పూర్తి పేరు* నమోదు చేయండి:",
        "reg_ask_backup_phone": "దయచేసి *మరొక ప్రత్యామ్నాయ ఫోన్ నంబర్* ఇవ్వండి (లేకపోతే *SKIP* అని టైప్ చేయండి):",
        "reg_ask_bands_count": "మీ కుటుంబానికి ఎన్ని బంధం రిస్ట్‌బ్యాండ్లు కావాలి? (1 నుండి 6 వరకు సంఖ్య నమోదు చేయండి):",
        "reg_ask_members": "పిల్లలు లేదా వృద్ధుల పేర్లు మరియు వయస్సు నమోదు చేయండి (ఉదాహరణ: 'ఆరవ్, వయస్సు 7; సీత, వయస్సు 70'):",
        "reg_success": (
            "✅ *రిజిస్ట్రేషన్ నమోదు పూర్తయింది!*\n\n"
            "📋 *రిజిస్ట్రేషన్ రిఫరెన్స్*: *{ref}*\n"
            "👤 *సంరక్షకుడు*: {name}\n"
            "📞 *మొబైల్ నంబర్*: {phone}\n"
            "🏷️ *రిస్ట్‌బ్యాండ్లు*: {count}\n\n"
            "⚠️ *ముఖ్యమైన తదుపరి చర్య*: రిస్ట్‌బ్యాండ్లు ఇంకా యాక్టివేట్ కాలేదు. దయచేసి కోటిలింగాల ఘాట్ లేదా పుష్కర ఘాట్ వద్ద గల అధికారిక *బంధం క్యూఆర్ స్టాల్* వద్దకు వెళ్లి ఈ రిఫరెన్స్ నంబర్ *{ref}* చూపించండి. మా సిబ్బంది మీ నంబర్ ధృవీకరించి, వాటర్‌ప్రూఫ్ రిస్ట్‌బ్యాండ్లు మరియు రహస్య *హ్యాండోవర్ పిన్ (PIN)* అందజేస్తారు."
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
        "missing_ask_details": "దయచేసి పిల్లల పేరు, వయస్సు, వేసుకున్న దుస్తుల రంగు మరియు చివరిగా ఎక్కడ చూశారో వివరాలు పంపండి:",
        "missing_case_created": (
            "🚨 *అత్యవసర మిస్సింగ్ హెచ్చరిక నమోదు చేయబడింది*\n\n"
            "కేస్ నంబర్: *{case_no}*\n"
            "వివరాలు: {details}\n"
            "స్థితి: *అన్ని ఘాట్ల హెల్ప్‌డెస్క్ రన్నర్లు మరియు పోలీస్ సిబ్బందికి BOLO జారీ చేయబడింది*\n\n"
            "📢 పబ్లిక్ అడ్రస్ సిస్టమ్ ద్వారా ప్రకటన చేయడానికి అధికారిక స్క్రిప్ట్ సిద్ధమైంది.\n"
            "📍 *తక్షణ చర్య*: దయచేసి వెంటనే కోటిలింగాల లేదా పుష్కర ఘాట్ వద్ద ఉన్న *పోలీస్ కంట్రోల్ బూత్* వద్దకు వెళ్లండి."
        ),
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
            "🌊 *గోదావరి పుష్కరాలు 2027 ముఖ్య ఘాట్ల వివరాలు*:\n\n"
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
            "📜 *ప్రభుత్వ అధికారిక సేవా రేట్ల వివరాలు (పుష్కరాలు 2027)*\n\n"
            "🚤 *పడవ ప్రయాణం (లైఫ్ జాకెట్ తప్పనిసరి)*:\n"
            "• సాధారణ ఫెర్రీ: ₹50 ఒక్కొక్కరికి\n"
            "• హావ్లాక్ బ్రిడ్జ్ ప్రత్యేక రైడ్ (30 నిమిషాలు): ₹150\n\n"
            "🛺 *ఆటో రిక్షా నిర్ణీత చార్జీలు*:\n"
            "• రాజమండ్రి స్టేషన్ నుండి పుష్కర ఘాట్: ₹60 స్థిర చార్జీ\n"
            "• కోటిలింగాల ఘాట్ నుండి సెంట్రల్ బస్ స్టాండ్: ₹80\n\n"
            "🧳 *క్లాక్‌రూమ్ బ్యాగ్ భద్రత*: 12 గంటలకు ₹20 ప్రతి బ్యాగ్‌కు\n\n"
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
            "📞 *అధికారిక పుష్కరాలు 24x7 ఎమర్జెన్సీ నంబర్లు*:\n\n"
            "🚨 *ఉచిత పుష్కర హెల్ప్‌లైన్*: 1800-425-2027\n"
            "👮 *పోలీస్ మరియు చైల్డ్ ప్రొటెక్షన్*: 112 / 0883-2422027\n"
            "🚑 *వైద్య సహాయం (అంబులెన్స్)*: 108 / 104\n\n"
            "ప్రతి ఘాట్ వద్ద పసుపు రంగు 'బంధం క్యూఆర్' బోర్డులు గల సహాయ కేంద్రాలు ఏర్పాటు చేయబడ్డాయి."
        ),
        "fallback": "క్షమించండి, మీ సందేశం అర్థం కాలేదు. ప్రధాన మెనూ కోసం *0* అని టైప్ చేయండి లేదా 1 నుండి 9 వరకు ఎంచుకోండి."
    },
    "hi": {
        "welcome": (
            "🙏 *गोदावरी पुष्करालु 2027 'बंधम' सहायक में आपका स्वागत है!*\n\n"
            "राजमंड्री और कोव्वूर घाटों पर श्रद्धालुओं की सुरक्षा व सहायता हेतु आधिकारिक डिजिटल सेवा।\n\n"
            "कृपया एक विकल्प चुनें (संख्या या पाठ भेजें):\n"
            "1️⃣ *बंधम क्यूआर (Bandham QR) परिवार पंजीकरण*\n"
            "2️⃣ *खोए हुए बच्चे / परिजन की आपातकालीन रिपोर्ट*\n"
            "3️⃣ *मुझे एक खोया हुआ बच्चा मिला है*\n"
            "4️⃣ *प्रमुख स्नान घाट व जन सुविधाएं*\n"
            "5️⃣ *शौचालय व स्वच्छता शिकायत*\n"
            "6️⃣ *आधिकारिक सेवा दरें (Approved Rates)*\n"
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
        "reg_ask_guardian_name": "कृपया *अभिभावक / परिवार के मुखिया का पूरा नाम* दर्ज करें:",
        "reg_ask_backup_phone": "कृपया एक *वैकल्पिक संपर्क नंबर* दर्ज करें (यदि नहीं है तो *SKIP* लिखें):",
        "reg_ask_bands_count": "परिवार के लिए कितने बंधम रिस्टबैंड चाहिए? (1 से 6 तक संख्या लिखें):",
        "reg_ask_members": "कृपया बच्चों या बुजुर्गों के नाम व आयु दर्ज करें (उदा. 'आरव, उम्र 7; सीता, उम्र 70'):",
        "reg_success": (
            "✅ *पंजीकरण सफलतापूर्वक दर्ज हुआ!*\n\n"
            "📋 *पंजीकरण संदर्भ*: *{ref}*\n"
            "👤 *अभिभावक*: {name}\n"
            "📞 *फ़ोन*: {phone}\n"
            "🏷️ *रिस्टबैंड संख्या*: {count}\n\n"
            "⚠️ *महत्वपूर्ण अगला कदम*: रिस्टबैंड अभी सक्रिय नहीं हैं। कृपया कोटिलिंगला या पुष्कर घाट पर स्थित *बंधम क्यूआर स्टॉल* पर जाकर संदर्भ *{ref}* दिखाएं। सत्यापन के पश्चात आपको वाटरप्रूफ रिस्टबैंड व गुप्त *रिलीज़ पिन (PIN)* प्रदान किया जाएगा।"
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
        "missing_ask_details": "कृपया बच्चे का नाम, उम्र, कपड़ों का रंग व अंतिम बार देखे जाने का स्थान लिखें:",
        "missing_case_created": (
            "🚨 *आपातकालीन अलर्ट दर्ज हुआ*\n\n"
            "केस संख्या: *{case_no}*\n"
            "विवरण: {details}\n"
            "स्थिति: *समस्त हेल्पडेस्क कर्मियों व पुलिस को BOLO अलर्ट प्रसारित*\n\n"
            "📢 लाउडस्पीकर प्रसारण हेतु तेलुगु उद्घोषणा तैयार की गई है। तुरंत नजदीकी पुलिस सहायता केंद्र पर संपर्क करें।"
        ),
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
            "🌊 *गोदावरी पुष्करालु 2027 प्रमुख घाट*:\n\n"
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
            "📜 *आधिकारिक अधिकृत दरें (पुष्करालु 2027)*\n\n"
            "🚤 *नाव यात्रा*: साधारण नौका ₹50 प्रति व्यक्ति (लाइफ जैकेट अनिवार्य)\n"
            "🛺 *ऑटो रिक्शा*: रेलवे स्टेशन से पुष्कर घाट ₹60 निर्धारित\n"
            "🧳 *क्लॉक रूम*: ₹20 प्रति बैग (12 घंटे)\n\n"
            "⚠️ अधिक पैसे मांगने पर तुरंत *7* दबाकर शिकायत दर्ज करें।"
        ),
        "scam_ask_category": "अधिक वसूली किस सेवा में हुई? (1. नाव 2. ऑटो 3. क्लॉक रूम 4. पूजा 5. अन्य):",
        "scam_ask_details": "कृपया वाहन/स्टॉल नंबर, वसूली गई राशि व स्थान का विवरण दें:",
        "scam_report_created": "✅ *शिकायत दर्ज: {report_no}*। स्पेशल एन्फोर्समेंट टीम को सूचित कर दिया गया है।",
        "helpdesk_info": (
            "📞 *24x7 आपातकालीन नंबर*:\n\n"
            "🚨 टोल-फ्री: 1800-425-2027\n"
            "👮 पुलिस व बाल सुरक्षा: 112 / 0883-2422027\n"
            "🚑 एम्बुलेंस: 108"
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

        # Universal resets and greetings
        greetings = [
            "0", "menu", "main menu", "మెనూ", "మేనూ", "मेनू", "reset", "start",
            "hi", "hello", "hey", "నమస్కారం", "నమస్తే", "హలో", "హాయ్",
            "नमस्ते", "प्रणाम", "ram ram", "pushkaralu", "bandham"
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
            context["guardian_name"] = text
            session.current_state = "REG_BACKUP_PHONE"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["reg_ask_backup_phone"]], lang, "REG_BACKUP_PHONE"

        if session.current_state == "REG_BACKUP_PHONE":
            backup = "" if text_lower in ["skip", "no", "వద్దు", "లేదు", "नहीं"] else text
            context["backup_phone"] = backup
            session.current_state = "REG_BANDS_COUNT"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["reg_ask_bands_count"]], lang, "REG_BANDS_COUNT"

        if session.current_state == "REG_BANDS_COUNT":
            nums = re.findall(r"\d+", text)
            count = int(nums[0]) if nums else 2
            count = max(1, min(count, 6))
            context["bands_count"] = count
            session.current_state = "REG_MEMBERS"
            session.context_data_json = json.dumps(context)
            await db.commit()
            return [TEXTS[lang]["reg_ask_members"]], lang, "REG_MEMBERS"

        if session.current_state == "REG_MEMBERS":
            context["members_desc"] = text
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
                members_json=json.dumps([{"notes": text}]),
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
            ) + TEXTS[lang]["menu_hint"]

            session.current_state = "MAIN_MENU"
            session.context_data_json = "{}"
            await db.commit()
            return [msg], lang, "MAIN_MENU"

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
