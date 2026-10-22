"""
ResQAI - NASA FIRMS (Fire Information for Resource Management System) Service
Integrates with NASA FIRMS active fire satellite detection API (VIIRS / MODIS)
with environment variable authentication and transparent standby handling.
"""

import os
import time
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

_FIRMS_CACHE: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes

MAP_KEY = os.environ.get("NASA_FIRMS_MAP_KEY", "").strip()

_INTEGRATION_STATUS = {
    'name': 'NASA FIRMS Satellite Thermal Anomaly Feed',
    'status': 'configured' if MAP_KEY else 'standby_key_required',
    'last_checked': None,
    'last_success': None,
    'last_error': None,
    'latency_ms': None,
    'auth_required': True,
    'key_configured': bool(MAP_KEY),
    'endpoint': 'https://firms.modaps.eosdis.nasa.gov/api/country/csv/',
    'request_key_url': 'https://firms.modaps.eosdis.nasa.gov/api/map_key/',
    'attribution': 'NASA Earth Science Data and Information System (ESDIS) / FIRMS',
    'disclaimer': 'Satellite fire detections indicate thermal anomalies detected by orbital sensors (VIIRS/MODIS) and are not automatically confirmed ground fires. Field verification is required.'
}


def get_integration_status() -> Dict[str, Any]:
    """Return status of NASA FIRMS integration."""
    status_copy = dict(_INTEGRATION_STATUS)
    status_copy['key_configured'] = bool(os.environ.get("NASA_FIRMS_MAP_KEY", "").strip())
    if not status_copy['key_configured']:
        status_copy['status'] = 'standby_key_required'
    return status_copy


def fetch_firms_fires(country_code: str = 'IND', days: int = 1, limit: int = 50) -> Dict[str, Any]:
    """
    Fetch satellite thermal detections for given country (default IND = India).
    Only queries live NASA API if a valid MAP_KEY is present in the environment.
    Never fabricates fire events when the key is absent.
    """
    global _INTEGRATION_STATUS

    active_key = os.environ.get("NASA_FIRMS_MAP_KEY", "").strip()
    if not active_key:
        _INTEGRATION_STATUS['status'] = 'standby_key_required'
        return {
            'status': 'INTEGRATION STANDBY (MAP_KEY REQUIRED)',
            'key_configured': False,
            'message': 'NASA FIRMS satellite fire detection is in standby mode. A free NASA MAP_KEY can be requested at https://firms.modaps.eosdis.nasa.gov/api/map_key/ and set in the backend environment as NASA_FIRMS_MAP_KEY.',
            'request_key_url': 'https://firms.modaps.eosdis.nasa.gov/api/map_key/',
            'returned_count': 0,
            'events': [],
            'attribution': _INTEGRATION_STATUS['attribution'],
            'disclaimer': _INTEGRATION_STATUS['disclaimer']
        }

    now = time.time()
    cache_id = f"firms_{country_code}_{days}_{limit}"
    if cache_id in _FIRMS_CACHE:
        c_time, c_data = _FIRMS_CACHE[cache_id]
        if now - c_time < CACHE_TTL_SECONDS:
            cached_res = dict(c_data)
            cached_res['cached'] = True
            return cached_res

    # FIRMS CSV Endpoint: https://firms.modaps.eosdis.nasa.gov/api/country/csv/[MAP_KEY]/[SOURCE]/[COUNTRY]/[DAY_RANGE]
    source = 'VIIRS_SNPP_NRT'
    url = f"https://firms.modaps.eosdis.nasa.gov/api/country/csv/{active_key}/{source}/{country_code}/{min(days, 3)}"

    start_t = time.time()
    _INTEGRATION_STATUS['last_checked'] = datetime.now(timezone.utc).isoformat()

    try:
        resp = requests.get(url, timeout=8.0)
        latency = int((time.time() - start_t) * 1000)
        _INTEGRATION_STATUS['latency_ms'] = latency

        if resp.status_code == 200:
            lines = resp.text.strip().split('\n')
            events = []

            if len(lines) > 1:
                header = [h.strip() for h in lines[0].split(',')]
                for line in lines[1:]:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) != len(header):
                        continue
                    row = dict(zip(header, parts))

                    lat = float(row.get('latitude', 0.0))
                    lon = float(row.get('longitude', 0.0))
                    bright = float(row.get('bright_ti4', row.get('brightness', 0.0)))
                    acq_date = row.get('acq_date', '')
                    acq_time = row.get('acq_time', '')
                    confidence = row.get('confidence', 'nominal')

                    dt_str = f"{acq_date}T{acq_time[:2]}:{acq_time[2:]}:00Z" if len(acq_time) >= 4 else datetime.now(timezone.utc).isoformat()

                    events.append({
                        'id': f"firms_{lat}_{lon}_{acq_date}",
                        'event_type': 'satellite_fire',
                        'title': f"Thermal Anomaly (Brightness {bright}K)",
                        'location_name': f"Orbital Detection ({lat:.3f}, {lon:.3f})",
                        'latitude': lat,
                        'longitude': lon,
                        'brightness': bright,
                        'confidence': confidence,
                        'satellite': row.get('satellite', 'Suomi-NPP VIIRS'),
                        'severity': 'high' if confidence == 'high' or bright > 350 else 'moderate',
                        'event_time': dt_str,
                        'retrieval_time': datetime.now(timezone.utc).isoformat(),
                        'source': 'NASA FIRMS VIIRS NRT',
                        'source_url': 'https://firms.modaps.eosdis.nasa.gov/',
                        'data_classification': 'satellite detection',
                        'verification_status': 'unverified'
                    })

                    if len(events) >= limit:
                        break

            _INTEGRATION_STATUS['status'] = 'operational'
            _INTEGRATION_STATUS['last_success'] = datetime.now(timezone.utc).isoformat()
            _INTEGRATION_STATUS['last_error'] = None

            result = {
                'status': 'LIVE DATA AVAILABLE',
                'key_configured': True,
                'country_code': country_code,
                'returned_count': len(events),
                'events': events,
                'attribution': _INTEGRATION_STATUS['attribution'],
                'disclaimer': _INTEGRATION_STATUS['disclaimer'],
                'cached': False
            }

            _FIRMS_CACHE[cache_id] = (now, result)
            return result
        else:
            _INTEGRATION_STATUS['status'] = 'degraded'
            _INTEGRATION_STATUS['last_error'] = f"HTTP {resp.status_code}"
            return {
                'status': 'SOURCE ERROR',
                'error': f"NASA FIRMS API returned HTTP {resp.status_code}. Please verify MAP_KEY quota.",
                'returned_count': 0,
                'events': [],
                'attribution': _INTEGRATION_STATUS['attribution']
            }

    except Exception as e:
        _INTEGRATION_STATUS['status'] = 'offline'
        _INTEGRATION_STATUS['last_error'] = str(e)
        return {
            'status': 'SOURCE UNAVAILABLE',
            'error': str(e),
            'returned_count': 0,
            'events': [],
            'attribution': _INTEGRATION_STATUS['attribution']
        }
