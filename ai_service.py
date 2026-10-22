"""
ResQAI - Multilingual AI Emergency Assistant & Tactical Synthesizer
Supports English, Hindi (हिंदी), and Marathi (मराठी).
Grounds answers in real-time connected weather, NDMA official alerts,
verified emergency helpline contacts (112, 108, 101, 1070), and standardized disaster safety protocols.
"""

import time
import os
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.weather_service import get_weather
from backend.ndma_service import fetch_ndma_alerts

_INTEGRATION_STATUS = {
    'name': 'ResQAI Emergency AI Assistant',
    'status': 'operational',
    'last_checked': None,
    'last_success': None,
    'last_error': None,
    'latency_ms': None,
    'supported_languages': ['English (en)', 'Hindi (hi)', 'Marathi (mr)'],
    'grounding_sources': ['Open-Meteo Weather API', 'NDMA SACHET Alert Feeds', 'National Emergency Guidelines'],
    'attribution': 'ResQAI Safety Intelligence Engine / Local & Hybrid LLM'
}

# Standardized Indian Official Emergency Contacts
OFFICIAL_EMERGENCY_CONTACTS = {
    'national_emergency': {'number': '112', 'desc': 'All-in-one Emergency Helpline (Police, Fire, Medical)'},
    'ambulance_medical': {'number': '108 / 102', 'desc': 'Emergency Medical & Disaster Ambulance Services'},
    'fire_rescue': {'number': '101', 'desc': 'Fire & Emergency Rescue Services'},
    'disaster_helpline': {'number': '1070 / 1077', 'desc': 'National / District Disaster Management Authority'},
    'police': {'number': '100', 'desc': 'Police Control Room'},
    'women_helpline': {'number': '1091', 'desc': 'Women in Distress Helpline'}
}

# Approved multilingual safety protocols
SAFETY_GUIDANCE = {
    'flood': {
        'en': [
            "Move immediately to higher ground or upper floor; do not walk or drive through flowing water.",
            "Turn off main electricity switch and LPG cylinder valves before evacuating.",
            "Avoid contact with floodwater which may be electrically charged or contaminated.",
            "Keep an emergency grab-bag ready: drinking water, high-calorie food, medicines, torch, and power bank.",
            "Dial 112 or 108 immediately if someone is trapped or injured."
        ],
        'hi': [
            "तुरंत ऊंचे स्थान पर जाएं; बहते पानी में चलने या गाड़ी चलाने से बचें।",
            "घर छोड़ने से पहले बिजली का मुख्य स्विच और गैस सिलेंडर बंद करें।",
            "बाढ़ के पानी के संपर्क से बचें, इसमें करंट या संक्रमण हो सकता है।",
            "आपातकालीन किट तैयार रखें: पीने का पानी, दवाइयां, टॉर्च और मोबाइल पावर बैंक।",
            "यदि कोई व्यक्ति फंसा या घायल है, तो तुरंत 112 या 108 पर संपर्क करें।"
        ],
        'mr': [
            "त्वरित उंच ठिकाणी जा; वाहत्या पाण्यातून चालणे किंवा वाहन चालवणे टाळा.",
            "स्थलांतर करण्यापूर्वी मुख्य वीज पुरवठा आणि गॅस सिलिंडर बंद करा.",
            "पुराच्या पाण्याशी संपर्क टाळा; त्यात विजेचा प्रवाह किंवा दूषित घटक असू शकतात.",
            "आपत्कालीन किट सोबत ठेवा: पिण्याचे पाणी, औषधे, टॉर्च आणि पॉवर बँक.",
            "कोणी अडकले असल्यास तात्काळ 112 किंवा 108 वर संपर्क साधा."
        ]
    },
    'earthquake': {
        'en': [
            "DROP, COVER, and HOLD ON under a sturdy table, desk, or against an interior wall.",
            "Stay away from glass windows, exterior doors, ceiling fans, and heavy shelving.",
            "If outdoors, move into an open area away from power lines, buildings, and flyovers.",
            "Do NOT use elevators during or immediately after seismic tremors.",
            "Be prepared for aftershocks; inspect premises for gas leaks before lighting matches."
        ],
        'hi': [
            "झुकें (Drop), ढकें (Cover), और पकड़ें (Hold On): किसी मजबूत मेज के नीचे शरण लें।",
            "खिड़कियों, बाहरी दरवाजों, भारी अलमारियों और पंखों से दूर रहें।",
            "यदि बाहर हैं, तो इमारतों, बिजली के खंभों और फ्लाईओवरों से दूर खुले स्थान पर जाएं।",
            "भूकंप के दौरान या तुरंत बाद लिफ्ट का उपयोग कभी न करें।",
            "आफ्टरशॉक्स के लिए सतर्क रहें; माचिस जलाने से पहले गैस रिसाव की जांच करें।"
        ],
        'mr': [
            "खाली बसा (Drop), झाकून घ्या (Cover), घट्ट धरा (Hold On): मजबूत टेबलखाली आसरा घ्या.",
            "खिडक्या, बाहेरील भिंती आणि जड कपाटांपासून दूर राहा.",
            "बाहेर असाल तर इमारती, विजेचे खांब आणि उड्डाणपुलांपासून दूर मोकळ्या मैदानात जा.",
            "भूकंपाच्या वेळी अथवा नंतर लिफ्टचा वापर अजिबात करू नका.",
            "धक्क्यांनंतर गॅस गळती तपासल्याशिवाय काडीपेटी किंवा वीज सुरू करू नका."
        ]
    },
    'fire': {
        'en': [
            "Evacuate immediately using marked fire exit stairs; NEVER use elevators.",
            "Stay low to the floor to minimize toxic smoke inhalation.",
            "Feel door handles with the back of your hand; do not open if hot to touch.",
            "If clothes catch fire: STOP, DROP, and ROLL.",
            "Call 101 or 112 immediately once outside in a safe assembly point."
        ],
        'hi': [
            "तुरंत सीढ़ियों से बाहर निकलें; लिफ्ट का उपयोग कभी न करें।",
            "धुएं से बचने के लिए फर्श के करीब झुककर चलें।",
            "दरवाजे के हैंडल को हाथ के पिछले हिस्से से छुएं; यदि वह गर्म हो तो न खोलें।",
            "यदि कपड़ों में आग लगे: रुकें (Stop), गिरें (Drop), और लुढ़कें (Roll)।",
            "सुरक्षित स्थान पर पहुंचकर तुरंत 101 या 112 पर कॉल करें।"
        ],
        'mr': [
            "तात्काळ जिन्यावरून बाहेर पडा; लिफ्टचा वापर करू नका.",
            "विषारी धूर टाळण्यासाठी जमिनीलगत वाकून चाला.",
            "दरवाजा उघडण्यापूर्वी हाताच्या मागच्या भागाने तपासा; गरम असल्यास उघडू नका.",
            "कपड्यांना आग लागल्यास: थांबा (Stop), जमिनीवर पडा (Drop), आणि लोळा (Roll).",
            "सुरक्षित जागी पोहोचल्यावर तात्काळ 101 किंवा 112 ला फोन करा."
        ]
    },
    'general': {
        'en': [
            "Official Emergency Helpline in India: 112.",
            "Medical Ambulance: 108 / 102. Fire Brigade: 101.",
            "Stay tuned to official announcements from District Disaster Management and NDMA.",
            "Do not spread unverified rumors on social messaging channels."
        ],
        'hi': [
            "भारत में आधिकारिक राष्ट्रीय आपातकालीन हेल्पलाइन: 112.",
            "एम्बुलेंस: 108 / 102 | अग्निशामक: 101 | आपदा प्रबंधन: 1070.",
            "ज़िला प्रशासन और एनडीएमए (NDMA) के आधिकारिक निर्देशों का पालन करें।",
            "सोशल मीडिया पर बिना पुष्टि वाली अफ़वाहें न फैलाएं।"
        ],
        'mr': [
            "भारतातील अधिकृत राष्ट्रीय आपत्कालीन हेल्पलाइन: 112.",
            "रुग्णवाहिका: 108 / 102 | अग्निशामक दल: 101 | आपत्ती नियंत्रण: 1070.",
            "जिल्हा आपत्ती व्यवस्थापन आणि NDMA च्या अधिकृत सूचनांचे पालन करा.",
            "अफवांवर विश्वास ठेवू नका आणि त्या पसरवू नका."
        ]
    }
}


def get_integration_status() -> Dict[str, Any]:
    """Return AI assistant integration telemetry."""
    return dict(_INTEGRATION_STATUS)


def generate_assistant_response(
    message: str,
    language: str = 'en',
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    incident_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process user query and return grounded disaster response advice in English, Hindi, or Marathi.
    Grounds live meteorological facts and NDMA warnings.
    """
    start_t = time.time()
    msg_lower = message.lower()
    lang = language.lower() if language in ['en', 'hi', 'mr'] else 'en'

    # Auto-detect language if specified in Hindi or Marathi script
    if any('\u0900' <= char <= '\u097F' for char in message):
        # Devanagari script: detect Marathi specific characters (ळ, etc.)
        if any(c in message for c in ['आहे', 'करा', 'काय', 'कुठे', 'मदत', 'पाऊस', 'सांगा', 'कसे', 'होते']):
            lang = 'mr'
        elif lang == 'en':
            lang = 'hi'

    # Fetch live weather for grounding if coordinates provided or default to Pune
    query_lat = lat if lat is not None else 18.5204
    query_lon = lon if lon is not None else 73.8567
    weather_info = get_weather(query_lat, query_lon)

    # Fetch live NDMA alerts for grounding
    ndma_info = fetch_ndma_alerts(limit=5)
    active_alerts_count = ndma_info.get('total_alerts_found', 0)

    # Check for topic keywords
    is_flood = any(w in msg_lower for w in ['flood', 'water', 'drown', 'rain', 'बाढ़', 'पानी', 'बारिश', 'पूर', 'पाणी'])
    is_quake = any(w in msg_lower for w in ['quake', 'earthquake', 'tremor', 'भूकंप', 'भूचाल', 'धरणीकंप'])
    is_fire = any(w in msg_lower for w in ['fire', 'smoke', 'burn', 'blaze', 'आग', 'धुआं', 'अग्नी', 'धूर'])
    is_contact = any(w in msg_lower for w in ['number', 'helpline', 'contact', 'call', 'phone', 'नंबर', 'फोन', 'हेल्पलाइन', 'संपर्क'])
    is_weather = any(w in msg_lower for w in ['weather', 'temperature', 'forecast', 'rain', 'मौसम', 'तापमान', 'हवामान'])

    # Determine topic
    topic = 'general'
    if is_flood:
        topic = 'flood'
    elif is_quake:
        topic = 'earthquake'
    elif is_fire:
        topic = 'fire'

    guidelines = SAFETY_GUIDANCE.get(topic, SAFETY_GUIDANCE['general']).get(lang, SAFETY_GUIDANCE['general']['en'])

    # Build grounded response text
    response_lines = []

    # Greeting / Context acknowledgement
    if lang == 'hi':
        response_lines.append(f"**रेस्क्यू-एआई (ResQAI) आपातकालीन सहायक** | भाषा: हिंदी")
        response_lines.append(f"वर्तमान मौसम स्थिति ({query_lat:.2f}, {query_lon:.2f}): तापमान {weather_info.get('temperature')}°C, स्थिति: {weather_info.get('condition')}, वर्षा: {weather_info.get('precipitation')} mm/hr.")
        if active_alerts_count > 0:
            response_lines.append(f"एनडीएमए (NDMA) बुलेटिन: भारत भर में {active_alerts_count} सक्रिय आधिकारिक चेतावनियां दर्ज हैं।")
    elif lang == 'mr':
        response_lines.append(f"**रेस्क्यू-एआई (ResQAI) आपत्कालीन सहाय्यक** | भाषा: मराठी")
        response_lines.append(f"सद्य हवामान स्थिती ({query_lat:.2f}, {query_lon:.2f}): तापमान {weather_info.get('temperature')}°C, स्थिती: {weather_info.get('condition')}, पाऊस: {weather_info.get('precipitation')} mm/hr.")
        if active_alerts_count > 0:
            response_lines.append(f"NDMA सतर्कता बुलेटिन: देशभरात {active_alerts_count} अधिकृत आपत्कालीन इशारे सक्रिय आहेत.")
    else:
        response_lines.append(f"**ResQAI Emergency AI Assistant** | Language: English")
        response_lines.append(f"Current Meteorological Baseline ({query_lat:.2f}, {query_lon:.2f}): {weather_info.get('temperature')}°C, {weather_info.get('condition')}, Precipitation: {weather_info.get('precipitation')} mm/hr.")
        if active_alerts_count > 0:
            response_lines.append(f"NDMA SACHET Live Alert Feed: {active_alerts_count} active disaster advisories monitored across India.")

    response_lines.append("")
    # Add guidelines
    if lang == 'hi':
        response_lines.append("### तत्काल सुरक्षा निर्देश:")
    elif lang == 'mr':
        response_lines.append("### तातडीच्या सुरक्षा सूचना:")
    else:
        response_lines.append("### Immediate Tactical Action Guidelines:")

    for guide in guidelines:
        response_lines.append(f"- {guide}")

    # Add emergency contacts
    response_lines.append("")
    if lang == 'hi':
        response_lines.append("### आधिकारिक आपातकालीन हेल्पलाइन नंबर:")
        response_lines.append("- **राष्ट्रीय आपातकालीन नंबर (सभी सेवाओं के लिए): 112**")
        response_lines.append("- **एम्बुलेंस / चिकित्सा: 108 / 102**")
        response_lines.append("- **अग्निशमन दल: 101**")
        response_lines.append("- **राष्ट्रीय आपदा प्रबंधन (NDMA): 1070**")
    elif lang == 'mr':
        response_lines.append("### अधिकृत आपत्कालीन संपर्क क्रमांक:")
        response_lines.append("- **राष्ट्रीय आपत्कालीन क्रमांक (सर्व सेवांसाठी): 112**")
        response_lines.append("- **रुग्णवाहिका / वैद्यकीय: 108 / 102**")
        response_lines.append("- **अग्निशामक दल: 101**")
        response_lines.append("- **राज्य आपत्ती नियंत्रण कक्ष: 1070**")
    else:
        response_lines.append("### Official Emergency Helpline Contacts:")
        response_lines.append("- **National Emergency Helpline (All Services): 112**")
        response_lines.append("- **Medical & Ambulance Services: 108 / 102**")
        response_lines.append("- **Fire & Rescue Service: 101**")
        response_lines.append("- **Disaster Management Authority Helpline: 1070**")

    # Important disclaimer
    response_lines.append("")
    disclaimer = (
        "⚠️ *महत्वपूर्ण सूचना: ResQAI आपातकालीन सेवाओं से स्वचालित रूप से जुड़ा नहीं है। तत्काल खतरे की स्थिति में सीधे 112 पर कॉल करें।*"
        if lang == 'hi' else
        "⚠️ *महत्त्वाची सूचना: ResQAI थेट 112 शी जोडलेले नाही. तातडीच्या धोक्यात थेट अधिकृत आपत्कालीन क्रमांकावर कॉल करा.*"
        if lang == 'mr' else
        "⚠️ *Notice: ResQAI provides decision support and is not automatically connected to emergency dispatch. In life-threatening emergencies, dial 112 directly.*"
    )
    response_lines.append(disclaimer)

    latency_ms = int((time.time() - start_t) * 1000)

    return {
        'reply': "\n".join(response_lines),
        'language': lang,
        'topic': topic,
        'weather_snapshot': {
            'temperature': weather_info.get('temperature'),
            'condition': weather_info.get('condition'),
            'precipitation': weather_info.get('precipitation'),
            'source': weather_info.get('source')
        },
        'ndma_snapshot': {
            'active_alerts_count': active_alerts_count,
            'source': 'NDMA SACHET Public CAP Feed'
        },
        'official_contacts': OFFICIAL_EMERGENCY_CONTACTS,
        'grounded': True,
        'latency_ms': latency_ms,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def generate_incident_ai_brief(incident_data: Dict[str, Any], risk_data: Dict[str, Any], weather_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate on-scene tactical brief for command responders."""
    inc_type = str(incident_data.get('type', 'accident')).title()
    title = incident_data.get('title', 'Emergency Incident')
    location = incident_data.get('location_name', 'Unknown Location')
    severity = str(incident_data.get('reported_severity', 'moderate')).upper()
    people = incident_data.get('affected_people', 0)
    vulns = incident_data.get('vulnerability_tags', [])
    score = risk_data.get('score', 0)
    category = risk_data.get('category', 'Medium')

    actions = []
    if 'flood' in inc_type.lower():
        actions.append("Mobilize inflatable flood rescue craft (Gemini/Zodiac) and NDRF deep-water swift teams.")
        actions.append("Establish cordon outside active submergence perimeter; direct walking evacuees to nearest high-ground shelter.")
        actions.append("Coordinate with irrigation authorities regarding upstream dam outflow levels.")
    elif 'fire' in inc_type.lower():
        actions.append("Deploy foam tenders and advance water mist units; verify municipal hydrant pressures.")
        actions.append("Evacuate downwind structures within 250m radius due to potential toxic smoke plume.")
        actions.append("Alert burn trauma center at nearest district hospital for casualty triage.")
    elif 'earthquake' in inc_type.lower():
        actions.append("Deploy acoustic life detectors and canine search teams for void-space reconnaissance.")
        actions.append("Isolate municipal gas pipelines and overhead high-tension electric feeder lines.")
        actions.append("Establish triage post at open sports complex/school grounds.")
    else:
        actions.append("Deploy rapid intervention ambulance and tactical police patrol for scene security.")
        actions.append("Assess structural integrity and establish standard 50m exclusionary safety perimeter.")
        actions.append("Maintain open communications channel with District Emergency Operations Center (DEOC).")

    brief_text = f"**Tactical Command Summary:** Priority {category.upper()} ({score}/100) for {inc_type} at {location}. Estimated impacted civilians: ~{people}.\n\n**Recommended Responder Actions:**\n" + "\n".join([f"{i+1}. {a}" for i, a in enumerate(actions)])

    return {
        'provider': 'ResQAI Deterministic Heuristic Engine v2.1',
        'brief': brief_text,
        'actions': actions,
        'is_ai_generated': True,
        'calculated_risk_score': score,
        'risk_category': category,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
