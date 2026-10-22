"""
ResQAI - Real-Time Multi-Source Disaster Aggregator
Normalizes and aggregates feeds from USGS Earthquakes, NDMA SACHET India Alerts,
Open-Meteo Extreme Weather, NASA FIRMS, and Verified Citizen Incident Reports.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import math

from backend.database import get_db, row_to_dict
from backend.earthquake_service import fetch_usgs_earthquakes
from backend.ndma_service import fetch_ndma_alerts
from backend.firms_service import fetch_firms_fires
from backend.weather_service import get_weather


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return round(r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 2)


def get_aggregated_disasters(
    hazard_type: Optional[str] = None,
    severity: Optional[str] = None,
    source_filter: Optional[str] = None,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    radius_km: Optional[float] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Aggregate all active real-time disaster streams into normalized records.
    """
    all_events: List[Dict[str, Any]] = []
    source_statuses: Dict[str, str] = {}

    # 1. USGS Earthquakes
    eq_res = fetch_usgs_earthquakes(feed_key='all_day', limit=40)
    source_statuses['usgs_earthquakes'] = eq_res.get('status', 'LIVE DATA AVAILABLE')
    for eq in eq_res.get('events', []):
        all_events.append({
            'id': eq['id'],
            'event_type': 'earthquake',
            'title': eq['title'],
            'location_name': eq['location_name'],
            'latitude': eq.get('latitude'),
            'longitude': eq.get('longitude'),
            'severity': eq.get('severity', 'moderate'),
            'magnitude': eq.get('magnitude'),
            'event_time': eq.get('event_time'),
            'retrieval_time': eq.get('retrieval_time'),
            'source': eq.get('source'),
            'source_url': eq.get('source_url'),
            'data_classification': 'earthquake event',
            'verification_status': 'verified',
            'details': f"Depth: {eq.get('depth_km')} km. Status: {eq.get('status')}"
        })

    # 2. NDMA SACHET India CAP Alerts
    ndma_res = fetch_ndma_alerts(limit=40)
    source_statuses['ndma_sachet'] = ndma_res.get('status', 'LIVE DATA AVAILABLE')
    for al in ndma_res.get('alerts', []):
        all_events.append({
            'id': al['id'],
            'event_type': 'official_alert',
            'title': al['title'],
            'location_name': al.get('source', 'India Region'),
            'latitude': al.get('latitude'),
            'longitude': al.get('longitude'),
            'severity': al.get('severity', 'high'),
            'magnitude': None,
            'event_time': al.get('published_at'),
            'retrieval_time': al.get('retrieval_time'),
            'source': al.get('source'),
            'source_url': al.get('source_url'),
            'data_classification': 'official alert',
            'verification_status': 'verified',
            'details': al.get('description', '')[:180]
        })

    # 3. NASA FIRMS Satellite Fire Detections
    firms_res = fetch_firms_fires(limit=25)
    source_statuses['nasa_firms'] = firms_res.get('status', 'INTEGRATION STANDBY')
    for fire in firms_res.get('events', []):
        all_events.append({
            'id': fire['id'],
            'event_type': 'fire',
            'title': fire['title'],
            'location_name': fire['location_name'],
            'latitude': fire.get('latitude'),
            'longitude': fire.get('longitude'),
            'severity': fire.get('severity', 'high'),
            'magnitude': fire.get('brightness'),
            'event_time': fire.get('event_time'),
            'retrieval_time': fire.get('retrieval_time'),
            'source': fire.get('source'),
            'source_url': fire.get('source_url'),
            'data_classification': 'satellite detection',
            'verification_status': 'unverified',
            'details': f"Satellite detection: {fire.get('satellite')}. Confidence: {fire.get('confidence')}"
        })

    # 4. Open-Meteo Severe Meteorological Anomaly Probe (Pune & Mumbai baseline)
    weather_pune = get_weather(18.5204, 73.8567)
    source_statuses['open_meteo'] = weather_pune.get('status', 'LIVE DATA AVAILABLE')
    if weather_pune.get('flood_threat_flag') or weather_pune.get('storm_threat_flag'):
        all_events.append({
            'id': 'weather_pune_anomaly',
            'event_type': 'severe_weather',
            'title': f"Meteorological Anomaly: {weather_pune.get('condition')}",
            'location_name': 'Pune Meteorological Region',
            'latitude': 18.5204,
            'longitude': 73.8567,
            'severity': 'high',
            'magnitude': weather_pune.get('precipitation'),
            'event_time': weather_pune.get('observation_time'),
            'retrieval_time': weather_pune.get('retrieval_time'),
            'source': 'Open-Meteo Meteorological Service',
            'source_url': 'https://open-meteo.com/',
            'data_classification': 'forecast',
            'verification_status': 'verified',
            'details': f"Rain: {weather_pune.get('precipitation')} mm/hr, Wind: {weather_pune.get('wind_speed')} km/h"
        })

    # 5. Citizen SOS Reports from SQLite
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents WHERE status != 'rejected' ORDER BY id DESC LIMIT 50")
            for inc_row in cursor.fetchall():
                inc = row_to_dict(inc_row)
                all_events.append({
                    'id': f"citizen_{inc['id']}",
                    'event_type': inc.get('type', 'other'),
                    'title': f"SOS: {inc.get('title')}",
                    'location_name': inc.get('location_name', 'Reported Location'),
                    'latitude': inc.get('latitude'),
                    'longitude': inc.get('longitude'),
                    'severity': inc.get('risk_category', 'Medium').lower(),
                    'magnitude': inc.get('calculated_risk_score'),
                    'event_time': inc.get('created_at'),
                    'retrieval_time': datetime.now(timezone.utc).isoformat(),
                    'source': f"Citizen SOS ({inc.get('incident_code')})",
                    'source_url': f"/#tab-tracking?code={inc.get('incident_code')}",
                    'data_classification': 'citizen report',
                    'verification_status': inc.get('status'),
                    'details': inc.get('description', '')[:180]
                })
    except Exception:
        pass

    # Apply filters
    filtered_events = []
    for evt in all_events:
        # Hazard type filter
        if hazard_type and hazard_type != 'all':
            if evt['event_type'].lower() != hazard_type.lower():
                continue

        # Severity filter
        if severity and severity != 'all':
            if evt['severity'].lower() != severity.lower():
                continue

        # Source filter
        if source_filter and source_filter != 'all':
            if source_filter.lower() not in evt['source'].lower() and source_filter.lower() not in evt['data_classification'].lower():
                continue

        # Distance filter
        if center_lat is not None and center_lon is not None and radius_km is not None:
            e_lat = evt.get('latitude')
            e_lon = evt.get('longitude')
            if e_lat is not None and e_lon is not None:
                dist = haversine_km(center_lat, center_lon, e_lat, e_lon)
                evt['distance_km'] = dist
                if dist > radius_km:
                    continue
            else:
                continue

        filtered_events.append(evt)

    # Sort: Critical first, then High, then time
    sev_rank = {'critical': 1, 'high': 2, 'moderate': 3, 'medium': 3, 'minor': 4, 'low': 4}
    filtered_events.sort(key=lambda x: (sev_rank.get(x['severity'].lower(), 5), x.get('event_time') or ''), reverse=False)

    return {
        'status': 'LIVE DATA AVAILABLE',
        'sources_status': source_statuses,
        'total_events': len(filtered_events),
        'events': filtered_events[:limit],
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'disclaimer': 'Aggregated disaster feed unifies verified official alerts, sensor feeds, and citizen reports. ResQAI does not invent casualty figures or ground fires.'
    }
