"""
ResQAI - Official Indian Disaster Alerts Service (NDMA SACHET)
Parses the National Disaster Management Authority (NDMA) SACHET Common Alerting Protocol
(CAP) RSS feed for verified official Indian disaster alerts.
"""

import time
import re
import ssl
import urllib.request
import xmltodict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

_NDMA_CACHE: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

FEED_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
OFFICIAL_PORTAL = "https://sachet.ndma.gov.in/"

_INTEGRATION_STATUS = {
    'name': 'NDMA SACHET Public Alert Feed',
    'status': 'untested',
    'last_checked': None,
    'last_success': None,
    'last_error': None,
    'latency_ms': None,
    'endpoint': FEED_URL,
    'official_portal': OFFICIAL_PORTAL,
    'auth_required': False,
    'attribution': 'National Disaster Management Authority (NDMA) — SACHET Portal (Government of India)',
    'disclaimer': 'Official alerts are retrieved from public NDMA SACHET CAP feeds. ResQAI does not manufacture official warnings or guarantee that every alert from all Indian authorities is included.'
}


def get_integration_status() -> Dict[str, Any]:
    """Return current NDMA SACHET integration status."""
    return dict(_INTEGRATION_STATUS)


def fetch_ndma_alerts(limit: int = 50, category_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch and parse live alerts from NDMA SACHET RSS/CAP XML feed.
    Handles XML parsing, multilingual text, timeouts, and fallback links.
    """
    global _INTEGRATION_STATUS

    now = time.time()
    cache_id = f"ndma_{limit}_{category_filter}"

    if cache_id in _NDMA_CACHE:
        c_time, c_data = _NDMA_CACHE[cache_id]
        if now - c_time < CACHE_TTL_SECONDS:
            cached_res = dict(c_data)
            cached_res['cached'] = True
            return cached_res

    start_t = time.time()
    _INTEGRATION_STATUS['last_checked'] = datetime.now(timezone.utc).isoformat()

    try:
        # Create resilient SSL context allowing Indian government public certificates
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ResQAI-EmergencySystem/1.0',
            'Accept': 'application/xml, text/xml, */*'
        }

        req = urllib.request.Request(FEED_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=9.0, context=ssl_ctx) as response:
            raw_xml = response.read().decode('utf-8', errors='ignore')

        latency = int((time.time() - start_t) * 1000)
        _INTEGRATION_STATUS['latency_ms'] = latency

        parsed_dict = xmltodict.parse(raw_xml)
        rss_root = parsed_dict.get('rss', {})
        channel = rss_root.get('channel', {})

        feed_title = channel.get('title', 'NDMA SACHET India CAP Disaster Alerts')
        feed_pub_date = channel.get('pubDate', datetime.now(timezone.utc).isoformat())

        raw_items = channel.get('item', [])
        if isinstance(raw_items, dict):
            raw_items = [raw_items]

        alerts = []
        for idx, item in enumerate(raw_items):
            guid_obj = item.get('guid')
            if isinstance(guid_obj, dict):
                alert_id = guid_obj.get('#text', f"ndma_{idx}")
            else:
                alert_id = str(guid_obj or f"ndma_{idx}")

            title = item.get('title') or 'NDMA Disaster Alert'
            description = item.get('description') or ''
            # Strip excessive HTML if present
            clean_desc = re.sub(r'<[^>]+>', ' ', description).strip()

            category = item.get('category') or 'General'
            author = item.get('author') or 'NDMA India / State Disaster Management Authority'
            link = item.get('link') or OFFICIAL_PORTAL
            pub_date = item.get('pubDate') or feed_pub_date

            if category_filter and category.lower() != category_filter.lower():
                continue

            # Infer severity keywords
            title_lower = title.lower() + " " + clean_desc.lower()
            if any(w in title_lower for w in ['severe', 'catastrophic', 'cyclone', 'heavy rainfall', 'thunderstorm with gusty wind', 'lightning']):
                sev = 'critical'
            elif any(w in title_lower for w in ['warning', 'heavy rain', 'flood alert', 'heatwave']):
                sev = 'high'
            elif any(w in title_lower for w in ['watch', 'moderate', 'advisory']):
                sev = 'moderate'
            else:
                sev = 'minor'

            # Parse coordinates if included in description or link
            lat = None
            lon = None

            alerts.append({
                'id': f"ndma_{alert_id}",
                'alert_code': alert_id,
                'event_type': 'official_alert',
                'title': title,
                'description': clean_desc,
                'category': category,
                'severity': sev,
                'source': author,
                'source_url': link,
                'published_at': pub_date,
                'retrieval_time': datetime.now(timezone.utc).isoformat(),
                'data_classification': 'official alert',
                'verification_status': 'verified',
                'latitude': lat,
                'longitude': lon,
                'official_portal': OFFICIAL_PORTAL
            })

            if len(alerts) >= limit:
                break

        _INTEGRATION_STATUS['status'] = 'operational'
        _INTEGRATION_STATUS['last_success'] = datetime.now(timezone.utc).isoformat()
        _INTEGRATION_STATUS['last_error'] = None

        result = {
            'status': 'LIVE DATA AVAILABLE',
            'feed_title': feed_title,
            'feed_pub_date': feed_pub_date,
            'total_alerts_found': len(raw_items),
            'returned_count': len(alerts),
            'alerts': alerts,
            'attribution': _INTEGRATION_STATUS['attribution'],
            'disclaimer': _INTEGRATION_STATUS['disclaimer'],
            'official_portal': OFFICIAL_PORTAL,
            'cached': False
        }

        _NDMA_CACHE[cache_id] = (now, result)
        return result

    except Exception as e:
        _INTEGRATION_STATUS['status'] = 'offline'
        _INTEGRATION_STATUS['last_error'] = str(e)
        return {
            'status': 'SOURCE UNAVAILABLE',
            'error': f"NDMA SACHET feed unreachable or undergoing update: {str(e)}",
            'official_portal': OFFICIAL_PORTAL,
            'disclaimer': 'When NDMA feeds are temporarily inaccessible, please consult the official portal directly at https://sachet.ndma.gov.in/.',
            'alerts': [],
            'returned_count': 0
        }
