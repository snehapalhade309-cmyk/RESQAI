"""
ResQAI - USGS Earthquake GeoJSON Feed Integration
Fetches and parses official USGS earthquake feeds, normalizing magnitude, coordinates,
depth, event URLs, and timestamps with deduplication and caching.
"""

import time
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Cache dictionary: feed_name -> (timestamp, data)
_EARTHQUAKE_CACHE: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

USGS_FEEDS = {
    'all_day': 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson',
    'all_hour': 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson',
    'all_week': 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson',
    '4.5_day': 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson',
    'significant_month': 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson'
}

_INTEGRATION_STATUS = {
    'name': 'USGS Earthquake Hazards Program',
    'status': 'untested',
    'last_checked': None,
    'last_success': None,
    'last_error': None,
    'latency_ms': None,
    'endpoint': USGS_FEEDS['all_day'],
    'auth_required': False,
    'rate_limit': 'Public access / reasonable polling',
    'attribution': 'U.S. Geological Survey (USGS) Earthquake Hazards Program',
    'coverage': 'Global seismic sensor network with M1.0+ comprehensive coverage in US and M4.0+ globally',
    'disclaimer': 'USGS earthquake records represent measured seismic events, not proof of structural damage or human casualties.'
}


def get_integration_status() -> Dict[str, Any]:
    """Return live status of USGS integration."""
    return dict(_INTEGRATION_STATUS)


def fetch_usgs_earthquakes(feed_key: str = 'all_day', min_magnitude: Optional[float] = None, limit: int = 60) -> Dict[str, Any]:
    """
    Fetch and normalize earthquake events from USGS GeoJSON feeds.
    """
    global _INTEGRATION_STATUS

    feed_url = USGS_FEEDS.get(feed_key, USGS_FEEDS['all_day'])
    now = time.time()

    # Check cache
    cache_id = f"{feed_key}_{min_magnitude}_{limit}"
    if cache_id in _EARTHQUAKE_CACHE:
        c_time, c_data = _EARTHQUAKE_CACHE[cache_id]
        if now - c_time < CACHE_TTL_SECONDS:
            cached_res = dict(c_data)
            cached_res['cached'] = True
            return cached_res

    start_t = time.time()
    _INTEGRATION_STATUS['last_checked'] = datetime.now(timezone.utc).isoformat()

    try:
        headers = {'User-Agent': 'ResQAI-DisasterResponse/1.0 (Emergency Decision Support)'}
        resp = requests.get(feed_url, headers=headers, timeout=6.0)
        latency = int((time.time() - start_t) * 1000)
        _INTEGRATION_STATUS['latency_ms'] = latency

        if resp.status_code == 200:
            payload = resp.json()
            metadata = payload.get('metadata', {})
            features = payload.get('features', [])

            events = []
            seen_ids = set()

            for feat in features:
                evt_id = feat.get('id')
                if not evt_id or evt_id in seen_ids:
                    continue
                seen_ids.add(evt_id)

                props = feat.get('properties', {})
                geom = feat.get('geometry', {})
                coords = geom.get('coordinates', [0, 0, 0])  # [lon, lat, depth]

                mag = props.get('mag')
                if mag is None:
                    mag = 0.0
                else:
                    try:
                        mag = round(float(mag), 1)
                    except (ValueError, TypeError):
                        mag = 0.0

                if min_magnitude is not None and mag < min_magnitude:
                    continue

                lon = float(coords[0]) if len(coords) > 0 else 0.0
                lat = float(coords[1]) if len(coords) > 1 else 0.0
                depth_km = round(float(coords[2]), 1) if len(coords) > 2 else 0.0

                # Event time is epoch ms
                epoch_ms = props.get('time', 0)
                event_time_iso = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).isoformat() if epoch_ms else datetime.now(timezone.utc).isoformat()

                # Categorize severity based on magnitude
                if mag >= 6.5:
                    sev = 'critical'
                elif mag >= 5.0:
                    sev = 'high'
                elif mag >= 3.5:
                    sev = 'moderate'
                else:
                    sev = 'minor'

                place = props.get('place') or 'Unknown Location'
                title = props.get('title') or f"M {mag} Earthquake - {place}"
                url = props.get('url') or f"https://earthquake.usgs.gov/earthquakes/eventpage/{evt_id}"

                events.append({
                    'id': f"usgs_{evt_id}",
                    'source_id': evt_id,
                    'event_type': 'earthquake',
                    'title': title,
                    'location_name': place,
                    'magnitude': mag,
                    'latitude': lat,
                    'longitude': lon,
                    'depth_km': depth_km,
                    'severity': sev,
                    'event_time': event_time_iso,
                    'retrieval_time': datetime.now(timezone.utc).isoformat(),
                    'source': 'USGS Earthquake Hazards Program',
                    'source_url': url,
                    'data_classification': 'earthquake event',
                    'verification_status': 'verified',
                    'tsunami_alert': bool(props.get('tsunami', 0)),
                    'status': props.get('status', 'reviewed')
                })

                if len(events) >= limit:
                    break

            _INTEGRATION_STATUS['status'] = 'operational'
            _INTEGRATION_STATUS['last_success'] = datetime.now(timezone.utc).isoformat()
            _INTEGRATION_STATUS['last_error'] = None

            feed_updated_ms = metadata.get('generated', 0)
            feed_updated_iso = datetime.fromtimestamp(feed_updated_ms / 1000.0, tz=timezone.utc).isoformat() if feed_updated_ms else datetime.now(timezone.utc).isoformat()

            result = {
                'status': 'LIVE DATA AVAILABLE',
                'feed_key': feed_key,
                'feed_title': metadata.get('title', 'USGS Earthquakes'),
                'feed_updated': feed_updated_iso,
                'total_events_in_feed': len(features),
                'returned_count': len(events),
                'events': events,
                'attribution': _INTEGRATION_STATUS['attribution'],
                'disclaimer': _INTEGRATION_STATUS['disclaimer'],
                'cached': False
            }

            _EARTHQUAKE_CACHE[cache_id] = (now, result)
            return result
        else:
            _INTEGRATION_STATUS['status'] = 'degraded'
            _INTEGRATION_STATUS['last_error'] = f"HTTP {resp.status_code}"
            return _get_fallback_earthquake_response(f"HTTP {resp.status_code}")

    except Exception as e:
        _INTEGRATION_STATUS['status'] = 'offline'
        _INTEGRATION_STATUS['last_error'] = str(e)
        return _get_fallback_earthquake_response(str(e))


def _get_fallback_earthquake_response(reason: str) -> Dict[str, Any]:
    """Fallback when USGS API is unreachable, maintaining honest data status."""
    return {
        'status': 'SOURCE UNAVAILABLE',
        'error': f"USGS GeoJSON feed temporarily unreachable: {reason}",
        'events': [],
        'returned_count': 0,
        'attribution': _INTEGRATION_STATUS['attribution'],
        'disclaimer': _INTEGRATION_STATUS['disclaimer'],
        'official_portal': 'https://earthquake.usgs.gov/'
    }
