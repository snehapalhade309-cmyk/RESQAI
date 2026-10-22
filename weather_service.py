"""
ResQAI - Climate & Weather Service
Integrates with Open-Meteo Public API (100% Free, No-Key-Required) with in-memory TTL caching,
3-day forecast projections, hourly meteorological metrics, geocoding search, and graceful offline fallback.
"""

import time
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# In-memory cache: (rounded_lat, rounded_lon) -> (timestamp, data)
_WEATHER_CACHE = {}
_GEOCODE_CACHE = {}
CACHE_TTL_SECONDS = 900  # 15 minutes

_INTEGRATION_STATUS = {
    'name': 'Open-Meteo Public Weather API',
    'status': 'untested',
    'last_checked': None,
    'last_success': None,
    'last_error': None,
    'latency_ms': None,
    'endpoint': 'https://api.open-meteo.com/v1/forecast',
    'geocoding_endpoint': 'https://geocoding-api.open-meteo.com/v1/search',
    'auth_required': False,
    'rate_limit': '10,000 requests/day (Free tier)',
    'attribution': 'Weather data by Open-Meteo.com under CC BY 4.0',
    'disclaimer': 'Forecast values represent meteorological model forecasts, not confirmed ground disasters.'
}

WMO_WEATHER_CODES = {
    0: 'Clear sky',
    1: 'Mainly clear',
    2: 'Partly cloudy',
    3: 'Overcast',
    45: 'Fog',
    48: 'Depositing rime fog',
    51: 'Light drizzle',
    53: 'Moderate drizzle',
    55: 'Dense drizzle',
    61: 'Slight rain',
    63: 'Moderate rain',
    65: 'Heavy rain',
    71: 'Slight snow fall',
    73: 'Moderate snow fall',
    75: 'Heavy snow fall',
    80: 'Slight rain showers',
    81: 'Moderate rain showers',
    82: 'Violent rain showers',
    95: 'Thunderstorm (Slight or moderate)',
    96: 'Thunderstorm with slight hail',
    99: 'Thunderstorm with heavy hail'
}


def get_integration_status() -> Dict[str, Any]:
    """Return live integration health information for System Health dashboard."""
    return dict(_INTEGRATION_STATUS)


def get_weather(lat: float, lon: float, include_forecast: bool = True) -> Dict[str, Any]:
    """
    Fetch current weather metrics and 3-day forecast for given coordinates.
    Returns structured weather observation with units, source, and retrieval timestamps.
    """
    global _INTEGRATION_STATUS

    if lat is None or lon is None:
        return _get_fallback_weather(lat, lon, "Coordinates not specified")

    cache_key = (round(float(lat), 2), round(float(lon), 2), include_forecast)
    now = time.time()

    if cache_key in _WEATHER_CACHE:
        cached_time, cached_data = _WEATHER_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            cached_copy = dict(cached_data)
            cached_copy['cached'] = True
            return cached_copy

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,showers,weather_code,wind_speed_10m,wind_direction_10m',
        'hourly': 'temperature_2m,precipitation_probability,precipitation,wind_speed_10m',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max',
        'forecast_days': 3,
        'timezone': 'auto'
    }

    start_t = time.time()
    _INTEGRATION_STATUS['last_checked'] = datetime.now(timezone.utc).isoformat()

    try:
        resp = requests.get(url, params=params, timeout=5.0)
        latency = int((time.time() - start_t) * 1000)
        _INTEGRATION_STATUS['latency_ms'] = latency

        if resp.status_code == 200:
            payload = resp.json()
            curr = payload.get('current', {})
            hourly = payload.get('hourly', {})
            daily = payload.get('daily', {})

            weather_code = curr.get('weather_code', 0)
            desc = WMO_WEATHER_CODES.get(weather_code, 'Atmospheric Condition Active')

            precip = float(curr.get('precipitation', 0.0))
            wind = float(curr.get('wind_speed_10m', 0.0))
            temp = float(curr.get('temperature_2m', 25.0))
            apparent_temp = float(curr.get('apparent_temperature', temp))
            humidity = float(curr.get('relative_humidity_2m', 60.0))

            # Threat indicators
            flood_threat = precip >= 15.0
            storm_threat = wind >= 40.0

            # Parse daily forecast cards
            daily_cards = []
            dates = daily.get('time', [])
            max_temps = daily.get('temperature_2m_max', [])
            min_temps = daily.get('temperature_2m_min', [])
            precip_sums = daily.get('precipitation_sum', [])
            w_codes = daily.get('weather_code', [])
            prob_maxs = daily.get('precipitation_probability_max', [])

            for i in range(len(dates)):
                d_code = w_codes[i] if i < len(w_codes) else 0
                daily_cards.append({
                    'date': dates[i],
                    'max_temp': max_temps[i] if i < len(max_temps) else temp,
                    'min_temp': min_temps[i] if i < len(min_temps) else temp - 5,
                    'precipitation_sum': precip_sums[i] if i < len(precip_sums) else 0.0,
                    'precip_prob_max': prob_maxs[i] if i < len(prob_maxs) else 0,
                    'weather_code': d_code,
                    'condition': WMO_WEATHER_CODES.get(d_code, 'Clear')
                })

            # Next 12 hours timeline
            hourly_preview = []
            h_times = hourly.get('time', [])[:12]
            h_temps = hourly.get('temperature_2m', [])[:12]
            h_probs = hourly.get('precipitation_probability', [])[:12]
            h_winds = hourly.get('wind_speed_10m', [])[:12]

            for i in range(len(h_times)):
                hourly_preview.append({
                    'time': h_times[i],
                    'temperature': h_temps[i] if i < len(h_temps) else temp,
                    'precip_prob': h_probs[i] if i < len(h_probs) else 0,
                    'wind_speed': h_winds[i] if i < len(h_winds) else wind
                })

            result = {
                'status': 'LIVE DATA AVAILABLE',
                'temperature': temp,
                'apparent_temperature': apparent_temp,
                'temperature_unit': '°C',
                'precipitation': precip,
                'precipitation_unit': 'mm/hr',
                'wind_speed': wind,
                'wind_speed_unit': 'km/h',
                'humidity': humidity,
                'humidity_unit': '%',
                'weather_code': weather_code,
                'condition': desc,
                'flood_threat_flag': flood_threat,
                'storm_threat_flag': storm_threat,
                'latitude': lat,
                'longitude': lon,
                'forecast_days': 3,
                'daily_forecast': daily_cards,
                'hourly_forecast': hourly_preview,
                'source': 'Open-Meteo Live API',
                'attribution': _INTEGRATION_STATUS['attribution'],
                'disclaimer': _INTEGRATION_STATUS['disclaimer'],
                'observation_time': curr.get('time', datetime.now(timezone.utc).isoformat()),
                'retrieval_time': datetime.now(timezone.utc).isoformat(),
                'cached': False
            }

            _WEATHER_CACHE[cache_key] = (now, result)
            _INTEGRATION_STATUS['status'] = 'operational'
            _INTEGRATION_STATUS['last_success'] = datetime.now(timezone.utc).isoformat()
            _INTEGRATION_STATUS['last_error'] = None
            return result
        else:
            err = f"Open-Meteo returned status {resp.status_code}"
            _INTEGRATION_STATUS['status'] = 'degraded'
            _INTEGRATION_STATUS['last_error'] = err
            return _get_fallback_weather(lat, lon, err)

    except Exception as e:
        err = f"Open-Meteo query failed: {str(e)}"
        _INTEGRATION_STATUS['status'] = 'offline'
        _INTEGRATION_STATUS['last_error'] = err
        return _get_fallback_weather(lat, lon, err)


def geocode_location(query: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Search location coordinates using Open-Meteo's official geocoding service.
    """
    q = query.strip()
    if not q or len(q) < 2:
        return []

    now = time.time()
    if q.lower() in _GEOCODE_CACHE:
        c_time, c_data = _GEOCODE_CACHE[q.lower()]
        if now - c_time < 3600:
            return c_data

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        'name': q,
        'count': count,
        'language': 'en',
        'format': 'json'
    }

    try:
        resp = requests.get(url, params=params, timeout=4.0)
        if resp.status_code == 200:
            results = resp.json().get('results', [])
            formatted = []
            for item in results:
                formatted.append({
                    'name': item.get('name'),
                    'latitude': item.get('latitude'),
                    'longitude': item.get('longitude'),
                    'country': item.get('country'),
                    'admin1': item.get('admin1', ''),
                    'display_name': f"{item.get('name')}, {item.get('admin1', '')}, {item.get('country', '')}".strip(', ')
                })
            _GEOCODE_CACHE[q.lower()] = (now, formatted)
            return formatted
    except Exception:
        pass

    # Regional anchor fallback for common Maharashtra / India cities
    known_anchors = {
        'pune': {'name': 'Pune', 'latitude': 18.5204, 'longitude': 73.8567, 'country': 'India', 'admin1': 'Maharashtra'},
        'mumbai': {'name': 'Mumbai', 'latitude': 19.0760, 'longitude': 72.8777, 'country': 'India', 'admin1': 'Maharashtra'},
        'delhi': {'name': 'Delhi', 'latitude': 28.6139, 'longitude': 77.2090, 'country': 'India', 'admin1': 'Delhi'},
        'bangalore': {'name': 'Bengaluru', 'latitude': 12.9716, 'longitude': 77.5946, 'country': 'India', 'admin1': 'Karnataka'},
        'nagpur': {'name': 'Nagpur', 'latitude': 21.1458, 'longitude': 79.0882, 'country': 'India', 'admin1': 'Maharashtra'},
        'nashik': {'name': 'Nashik', 'latitude': 19.9975, 'longitude': 73.7898, 'country': 'India', 'admin1': 'Maharashtra'}
    }

    matches = []
    q_low = q.lower()
    for k, v in known_anchors.items():
        if q_low in k or k in q_low:
            matches.append({
                'name': v['name'],
                'latitude': v['latitude'],
                'longitude': v['longitude'],
                'country': v['country'],
                'admin1': v['admin1'],
                'display_name': f"{v['name']}, {v['admin1']}, {v['country']}"
            })
    return matches


def _get_fallback_weather(lat: Optional[float], lon: Optional[float], reason: str = "") -> Dict[str, Any]:
    """Provides safe baseline weather estimates when remote service is unavailable."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        'status': 'SIMULATED TEST DATA',
        'temperature': 26.5,
        'apparent_temperature': 27.0,
        'temperature_unit': '°C',
        'precipitation': 0.0,
        'precipitation_unit': 'mm/hr',
        'wind_speed': 12.0,
        'wind_speed_unit': 'km/h',
        'humidity': 65.0,
        'humidity_unit': '%',
        'weather_code': 1,
        'condition': 'Mainly Clear (Estimated Baseline)',
        'flood_threat_flag': False,
        'storm_threat_flag': False,
        'latitude': lat if lat is not None else 18.5204,
        'longitude': lon if lon is not None else 73.8567,
        'forecast_days': 3,
        'daily_forecast': [
            {'date': now_iso[:10], 'max_temp': 28.0, 'min_temp': 22.0, 'precipitation_sum': 0.0, 'precip_prob_max': 10, 'weather_code': 1, 'condition': 'Mainly clear'},
            {'date': 'Tomorrow', 'max_temp': 29.0, 'min_temp': 23.0, 'precipitation_sum': 1.2, 'precip_prob_max': 25, 'weather_code': 2, 'condition': 'Partly cloudy'},
            {'date': 'Day After', 'max_temp': 27.5, 'min_temp': 21.5, 'precipitation_sum': 4.0, 'precip_prob_max': 40, 'weather_code': 3, 'condition': 'Overcast'}
        ],
        'hourly_forecast': [],
        'source': 'ResQAI Climate Baseline (Offline Safe Fallback)',
        'attribution': 'Local deterministic meteorological estimate',
        'disclaimer': _INTEGRATION_STATUS['disclaimer'],
        'observation_time': now_iso,
        'retrieval_time': now_iso,
        'cached': False,
        'fallback_reason': reason
    }
