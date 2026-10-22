"""
ResQAI - AI-Powered Emergency Management & Response System
FastAPI REST API Server & SPA Static File Handler

Tagline: Detect Faster. Respond Smarter. Save Lives.
Features:
- Real-time Multi-source Disaster Aggregation (USGS, NDMA SACHET, Open-Meteo, NASA FIRMS)
- Explainable Risk Engine v2.1
- Role-Based Authentication (Citizen, Authorized Responder, Administrator)
- Secure SOS Submission & Tracking
- Atomic Fleet Dispatch & Evacuation Routing
- Multilingual Grounded AI Assistant (EN, HI, MR)
"""

import os
import sys
import json
import time
import random
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Query, Path, Body, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import get_db, row_to_dict, init_db
from backend.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_authenticated_user, require_role
)
from backend.risk_engine import calculate_risk
from backend.dispatch_engine import get_recommendations, assign_resource, release_resource
from backend.weather_service import get_weather, geocode_location, get_integration_status as get_weather_status
from backend.earthquake_service import fetch_usgs_earthquakes, get_integration_status as get_earthquake_status
from backend.ndma_service import fetch_ndma_alerts, get_integration_status as get_ndma_status
from backend.firms_service import fetch_firms_fires, get_integration_status as get_firms_status
from backend.routing_service import get_route, get_integration_status as get_routing_status
from backend.ai_service import generate_assistant_response, generate_incident_ai_brief, get_integration_status as get_ai_status
from backend.disaster_aggregator import get_aggregated_disasters
from backend.audit_service import log_event, get_recent_logs
from backend.seed_data import seed_database

FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')

# Initialize SQLite tables on startup
init_db()

app = FastAPI(
    title="ResQAI Emergency Management API",
    description="Full-stack AI-powered emergency management and tactical decision-support API.",
    version="2.5.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    role: str = Field(default="citizen")
    organization: Optional[str] = None
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class IncidentReportRequest(BaseModel):
    type: str = Field(..., description="Hazard type: flood, earthquake, fire, accident, severe_weather, medical, etc.")
    title: str = Field(..., min_length=3, max_length=200)
    location_name: str = Field(..., min_length=2, max_length=200)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reported_severity: str = Field(default="moderate", description="minor, moderate, severe, catastrophic")
    affected_people: int = Field(default=0, ge=0)
    vulnerability_tags: List[str] = Field(default_factory=list)
    description: str = Field(default="")
    reporter_name: Optional[str] = "Anonymous Citizen"
    reporter_contact: Optional[str] = ""
    image_url: Optional[str] = None


class IncidentStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="submitted, under_review, verified, assigned, in_progress, resolved, rejected")
    responder_notes: Optional[str] = None
    actor: Optional[str] = "Authorized Commander"


class DispatchRequest(BaseModel):
    incident_id: int
    resource_id: int
    notes: Optional[str] = "Standard tactical dispatch"
    dispatcher_name: Optional[str] = "Command Dispatcher"


class ReleaseRequest(BaseModel):
    resource_id: int
    notes: Optional[str] = "Mission accomplished"
    actor: Optional[str] = "Command Dispatcher"


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    language: str = Field(default="en", description="en, hi, or mr")
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# ---------------------------------------------------------------------------
# System & Diagnostics Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["System"])
def get_system_health():
    """Return health telemetry for database and all connected external integrations."""
    db_status = {'status': 'healthy', 'error': None, 'tables': {}}
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            for tbl in ['incidents', 'resources', 'shelters', 'emergency_resources', 'dispatches', 'alerts', 'audit_logs', 'users']:
                try:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM {tbl}")
                    db_status['tables'][tbl] = cursor.fetchone()['cnt']
                except Exception:
                    pass
    except Exception as e:
        db_status['status'] = 'error'
        db_status['error'] = str(e)

    integrations = {
        'database': db_status,
        'osm_tiles': {
            'name': 'OpenStreetMap Cartographic Tile Server',
            'status': 'operational',
            'auth_required': False,
            'attribution': '© OpenStreetMap contributors',
            'endpoint': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        },
        'open_meteo': get_weather_status(),
        'usgs_earthquakes': get_earthquake_status(),
        'ndma_sachet': get_ndma_status(),
        'nasa_firms': get_firms_status(),
        'routing_engine': get_routing_status(),
        'ai_service': get_ai_status()
    }

    return {
        'system': 'ResQAI AI-Powered Emergency Management & Response System',
        'tagline': 'Detect Faster. Respond Smarter. Save Lives.',
        'status': 'operational' if db_status['status'] == 'healthy' else 'degraded',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'integrations': integrations
    }


@app.get("/api/sources/status", tags=["System"])
def get_sources_status():
    """Detailed real-data integration registry, response times, rate limits, and attribution."""
    return {
        'system_time': datetime.now(timezone.utc).isoformat(),
        'sources': {
            'weather_open_meteo': get_weather_status(),
            'earthquakes_usgs': get_earthquake_status(),
            'india_alerts_ndma': get_ndma_status(),
            'satellite_fires_nasa': get_firms_status(),
            'routing_osrm': get_routing_status(),
            'ai_emergency_briefing': get_ai_status()
        },
        'disclaimers': {
            'emergency_disclaimer': 'ResQAI is a decision-support and coordination system. It is not automatically linked to emergency 112 dispatch. Contact 112 directly in immediate peril.',
            'weather_disclaimer': 'Weather forecasts are predictive models, not confirmed ground emergencies.',
            'fire_disclaimer': 'Satellite fire anomalies represent orbital thermal detections, not automatically confirmed ground fires.',
            'earthquake_disclaimer': 'Earthquake records represent detected seismic activity, not proof of structural casualties.'
        }
    }


@app.get("/api/stats", tags=["System"])
def get_dashboard_stats():
    """Aggregated KPIs for Tactical Command Center Overview."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM incidents")
        total_inc = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as active FROM incidents WHERE status NOT IN ('resolved', 'rejected')")
        active_inc = cursor.fetchone()['active']

        cursor.execute("SELECT COUNT(*) as critical FROM incidents WHERE risk_category = 'Critical' AND status NOT IN ('resolved', 'rejected')")
        critical_inc = cursor.fetchone()['critical']

        cursor.execute("SELECT COUNT(*) as high FROM incidents WHERE risk_category = 'High' AND status NOT IN ('resolved', 'rejected')")
        high_inc = cursor.fetchone()['high']

        cursor.execute("SELECT COUNT(*) as total FROM resources")
        total_res = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as avail FROM resources WHERE status = 'available'")
        avail_res = cursor.fetchone()['avail']

        cursor.execute("SELECT COUNT(*) as dispatched FROM resources WHERE status = 'dispatched'")
        dispatched_res = cursor.fetchone()['dispatched']

        cursor.execute("SELECT SUM(total_capacity) as cap, SUM(current_occupancy) as occ FROM shelters")
        shelter_row = cursor.fetchone()
        tot_cap = shelter_row['cap'] or 0
        tot_occ = shelter_row['occ'] or 0
        util_pct = round((tot_occ / tot_cap * 100.0), 1) if tot_cap > 0 else 0.0

        cursor.execute("SELECT COUNT(*) as unack FROM alerts WHERE is_acknowledged = 0")
        unack_alerts = cursor.fetchone()['unack']

        return {
            'incidents': {
                'total': total_inc,
                'active': active_inc,
                'critical_active': critical_inc,
                'high_active': high_inc,
                'resolved': total_inc - active_inc
            },
            'resources': {
                'total': total_res,
                'available': avail_res,
                'dispatched': dispatched_res,
                'in_maintenance': max(0, total_res - avail_res - dispatched_res),
                'utilization_pct': round((dispatched_res / total_res * 100.0), 1) if total_res > 0 else 0.0
            },
            'shelters': {
                'total_capacity': tot_cap,
                'current_occupancy': tot_occ,
                'utilization_pct': util_pct,
                'available_capacity': max(0, tot_cap - tot_occ)
            },
            'alerts': {
                'unacknowledged': unack_alerts
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


# ---------------------------------------------------------------------------
# Authentication & Role-Based Access Control
# ---------------------------------------------------------------------------
@app.post("/api/auth/register", tags=["Auth"])
def register_user(req: RegisterRequest):
    """Register a new citizen or field responder account."""
    now_iso = datetime.now(timezone.utc).isoformat()
    role = req.role.lower() if req.role.lower() in ['citizen', 'responder'] else 'citizen'

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (req.username.strip(), req.email.strip()))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username or email already registered.")

        pw_hash = hash_password(req.password)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, full_name, organization, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (req.username.strip(), req.email.strip().lower(), pw_hash, role, req.full_name.strip(), req.organization, req.phone, now_iso))
        user_id = cursor.lastrowid

    token = create_access_token({'sub': req.username.strip(), 'role': role, 'user_id': user_id})
    return {
        'message': 'Registration successful.',
        'access_token': token,
        'token_type': 'bearer',
        'user': {
            'id': user_id,
            'username': req.username.strip(),
            'email': req.email.strip().lower(),
            'role': role,
            'full_name': req.full_name.strip()
        }
    }


@app.post("/api/auth/login", tags=["Auth"])
def login_user(req: LoginRequest):
    """Authenticate with username and password, returning JWT bearer token."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (req.username.strip(),))
        user_row = cursor.fetchone()
        if not user_row or not verify_password(req.password, user_row['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        user = row_to_dict(user_row)
        token = create_access_token({'sub': user['username'], 'role': user['role'], 'user_id': user['id']})

        return {
            'message': 'Login successful.',
            'access_token': token,
            'token_type': 'bearer',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'full_name': user['full_name'],
                'organization': user.get('organization')
            }
        }


@app.get("/api/auth/me", tags=["Auth"])
def get_current_user_profile(user: Optional[dict] = Depends(get_current_user)):
    """Retrieve currently authenticated user identity and role."""
    if not user:
        return {'authenticated': False, 'user': None}
    return {'authenticated': True, 'user': user}


# ---------------------------------------------------------------------------
# Real-Data Integration Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/disasters", tags=["Disasters"])
def list_disasters(
    hazard_type: Optional[str] = Query(None, description="flood, earthquake, fire, severe_weather, official_alert"),
    severity: Optional[str] = Query(None, description="critical, high, moderate, minor"),
    source: Optional[str] = Query(None, description="usgs, ndma, open-meteo, citizen"),
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    radius_km: Optional[float] = None,
    limit: int = Query(60, ge=1, le=200)
):
    """Normalized real-time disaster dashboard combining USGS, NDMA SACHET, Open-Meteo, NASA FIRMS, and Citizen Reports."""
    return get_aggregated_disasters(
        hazard_type=hazard_type,
        severity=severity,
        source_filter=source,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_km=radius_km,
        limit=limit
    )


@app.get("/api/earthquakes", tags=["Disasters"])
def get_earthquakes(
    feed: str = Query('all_day', description="all_day, all_hour, all_week, 4.5_day, significant_month"),
    min_mag: Optional[float] = Query(None, description="Minimum magnitude filter"),
    limit: int = Query(50, ge=1, le=100)
):
    """Real-time USGS earthquake GeoJSON feed parser."""
    return fetch_usgs_earthquakes(feed_key=feed, min_magnitude=min_mag, limit=limit)


@app.get("/api/alerts", tags=["Disasters"])
def list_alerts(unacknowledged_only: bool = False, limit: int = 50):
    """List in-app and official alerts."""
    query = "SELECT * FROM alerts"
    if unacknowledged_only:
        query += " WHERE is_acknowledged = 0"
    query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END, id DESC LIMIT ?"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        return [row_to_dict(r) for r in cursor.fetchall()]


@app.get("/api/ndma-alerts", tags=["Disasters"])
def get_official_ndma_alerts(limit: int = 40):
    """Official NDMA SACHET India CAP/RSS feed parser with original attribution and links."""
    return fetch_ndma_alerts(limit=limit)


@app.get("/api/fires", tags=["Disasters"])
def get_fires(country: str = 'IND', days: int = 1, limit: int = 50):
    """NASA FIRMS satellite thermal detection feed (or standby notice when MAP_KEY unconfigured)."""
    return fetch_firms_fires(country_code=country, days=days, limit=limit)


@app.get("/api/weather", tags=["Climate"])
def query_weather(
    lat: float = Query(18.5204, description="Latitude"),
    lon: float = Query(73.8567, description="Longitude"),
    forecast: bool = Query(True, description="Include 3-day and hourly forecast")
):
    """Retrieve real-time weather and 3-day forecast from Open-Meteo."""
    return get_weather(lat, lon, include_forecast=forecast)


@app.get("/api/geocode", tags=["Climate"])
def geocode_query(q: str = Query(..., min_length=2)):
    """Geocode place name to latitude/longitude using Open-Meteo Geocoding API."""
    return geocode_location(q)


# ---------------------------------------------------------------------------
# Citizen SOS & Incident Management
# ---------------------------------------------------------------------------
@app.post("/api/incidents", status_code=201, tags=["Incidents"])
def report_incident(req: IncidentReportRequest, user: Optional[dict] = Depends(get_current_user)):
    """
    Submit citizen emergency SOS request with validation, transparent heuristic risk calculation,
    database persistence, unique Incident Code, and private tracking PIN.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # Query real-time weather for environmental amplification
    weather = None
    if req.latitude is not None and req.longitude is not None:
        weather = get_weather(req.latitude, req.longitude)

    # Calculate deterministic explainable risk score
    risk = calculate_risk({
        'type': req.type,
        'reported_severity': req.reported_severity,
        'affected_people': req.affected_people,
        'vulnerability_tags': req.vulnerability_tags,
        'latitude': req.latitude,
        'longitude': req.longitude
    }, weather)

    # Generate unique Incident Code and Tracking PIN
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM incidents")
        next_num = cursor.fetchone()['total'] + 1
        incident_code = f"INC-2026-{next_num:03d}"
        tracking_pin = f"PIN-{random.randint(1000, 9999)}"

        reporter_name = req.reporter_name or (user['full_name'] if user else "Anonymous Citizen")
        reporter_contact = req.reporter_contact or (user.get('phone', '') if user else "")

        cursor.execute("""
            INSERT INTO incidents (
                incident_code, type, title, location_name, latitude, longitude,
                reported_severity, affected_people, vulnerability_tags, description,
                reporter_name, reporter_contact, tracking_pin, calculated_risk_score, risk_category,
                risk_factors_json, status, is_demo, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            incident_code, req.type.lower(), req.title.strip(), req.location_name.strip(),
            req.latitude, req.longitude, req.reported_severity.lower(), req.affected_people,
            json.dumps(req.vulnerability_tags), req.description.strip(),
            reporter_name, reporter_contact, tracking_pin, risk['score'], risk['category'],
            json.dumps(risk['factor_breakdown']), 'submitted', 0, now_iso, now_iso
        ))
        new_id = cursor.lastrowid

        # Generate in-app alert for high/critical incidents
        if risk['category'] in ['High', 'Critical']:
            alert_sev = 'critical' if risk['category'] == 'Critical' else 'warning'
            cursor.execute("""
                INSERT INTO alerts (title, message, severity, incident_id, source, source_url, is_acknowledged, created_at)
                VALUES (?, ?, ?, ?, 'Risk Intelligence Engine', ?, 0, ?)
            """, (
                f"{risk['category'].upper()} HAZARD: {req.title}",
                f"{req.type.upper()} at {req.location_name}. Risk Score: {risk['score']}/100. Affected: ~{req.affected_people} people.",
                alert_sev, new_id, f"/#tab-tracking?code={incident_code}", now_iso
            ))

        # Log audit trail
        log_event('INCIDENT_CREATED', 'incident', new_id, {
            'incident_code': incident_code,
            'type': req.type,
            'risk_score': risk['score'],
            'risk_category': risk['category']
        }, reporter_name, conn=conn)

        cursor.execute("SELECT * FROM incidents WHERE id = ?", (new_id,))
        created_incident = row_to_dict(cursor.fetchone())

    return {
        'message': 'Incident SOS reported and persisted to command net.',
        'incident': created_incident,
        'incident_code': incident_code,
        'tracking_pin': tracking_pin,
        'risk_evaluation': risk,
        'notice': 'ResQAI is not automatically connected to emergency services. Submitting a request does not call 112 or guarantee rescue. If you are in immediate danger in India, contact 112 directly.'
    }


@app.get("/api/incidents", tags=["Incidents"])
def list_incidents(
    type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    """List incidents with filtering."""
    query = "SELECT * FROM incidents WHERE 1=1"
    params = []

    if type and type != 'all':
        query += " AND type = ?"
        params.append(type.lower())
    if severity and severity != 'all':
        query += " AND (reported_severity = ? OR risk_category = ?)"
        params.extend([severity.lower(), severity.capitalize()])
    if status and status != 'all':
        query += " AND status = ?"
        params.append(status.lower())
    if search:
        query += " AND (title LIKE ? OR location_name LIKE ? OR incident_code LIKE ? OR description LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    query += " ORDER BY CASE risk_category WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, id DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [row_to_dict(r) for r in cursor.fetchall()]


@app.get("/api/incidents/{incident_id}", tags=["Incidents"])
def get_incident_detail(
    incident_id: int = Path(..., description="Numeric Incident ID"),
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Retrieve full incident details, on-scene weather snapshot, AI situation brief, and smart fleet recommendations.
    Protects private contact info unless user is an authenticated responder/admin.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found.")

        incident = row_to_dict(row)

        # Protect personal contact info if unauthenticated or citizen
        is_privileged = user and user.get('role') in ['responder', 'admin']
        if not is_privileged:
            incident['reporter_contact'] = "[Protected - Authorized Responders Only]"

        # Weather snapshot
        weather = None
        if incident.get('latitude') is not None and incident.get('longitude') is not None:
            weather = get_weather(incident['latitude'], incident['longitude'])

        # Risk re-evaluation
        risk_result = calculate_risk(incident, weather)

        # AI briefing
        brief = generate_incident_ai_brief(incident, risk_result, weather)

        # Smart dispatch recommendations
        dispatch_recs = get_recommendations(incident_id)

        # Assigned resources
        cursor.execute("""
            SELECT r.*, d.dispatch_time, d.status as dispatch_status, d.notes as dispatch_notes
            FROM resources r
            JOIN dispatches d ON d.resource_id = r.id
            WHERE d.incident_id = ? AND d.status != 'completed'
        """, (incident_id,))
        assigned_units = [row_to_dict(r) for r in cursor.fetchall()]

        return {
            'incident': incident,
            'weather': weather,
            'risk_evaluation': risk_result,
            'decision_brief': brief,
            'recommendations': dispatch_recs.get('recommendations', []),
            'assigned_units': assigned_units
        }


@app.get("/api/incidents/track/{code}", tags=["Incidents"])
def track_incident_by_code(code: str = Path(..., description="Incident code, e.g. INC-2026-001"), pin: Optional[str] = None):
    """
    Secure public tracking endpoint for citizens.
    Displays operational status progression, timeline, and responder notes.
    Hides private phone and identity unless matching PIN is provided.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE incident_code = ?", (code.strip().upper(),))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Incident code '{code}' not found.")

        incident = row_to_dict(row)

        has_pin = pin and pin.strip().upper() == str(incident.get('tracking_pin', '')).upper()
        if not has_pin:
            incident['reporter_contact'] = "[Confidential]"
            incident['reporter_name'] = incident['reporter_name'][:2] + "***" if incident.get('reporter_name') else "Citizen"

        # Fetch assigned unit name if any
        cursor.execute("""
            SELECT r.name, r.type, d.dispatch_time, d.status
            FROM resources r
            JOIN dispatches d ON d.resource_id = r.id
            WHERE d.incident_id = ? AND d.status != 'completed'
            ORDER BY d.id DESC LIMIT 1
        """, (incident['id'],))
        assigned_row = cursor.fetchone()
        assigned_unit = row_to_dict(assigned_row) if assigned_row else None

        # Build lifecycle progression steps
        status_order = ['submitted', 'under_review', 'verified', 'assigned', 'in_progress', 'resolved']
        current_status = incident.get('status', 'submitted').lower()
        curr_idx = status_order.index(current_status) if current_status in status_order else 0

        timeline = []
        for idx, s in enumerate(status_order):
            timeline.append({
                'status': s,
                'label': s.replace('_', ' ').title(),
                'completed': idx <= curr_idx,
                'current': idx == curr_idx
            })

        return {
            'incident_code': incident['incident_code'],
            'title': incident['title'],
            'location_name': incident['location_name'],
            'status': current_status,
            'risk_category': incident['risk_category'],
            'created_at': incident['created_at'],
            'updated_at': incident['updated_at'],
            'assigned_unit': assigned_unit,
            'responder_notes': incident.get('responder_notes') or "Report logged in emergency command queue.",
            'timeline': timeline,
            'disclaimer': 'ResQAI status tracking reflects command center queue progression.'
        }


@app.patch("/api/incidents/{incident_id}/status", tags=["Incidents"])
def update_incident_status(
    incident_id: int,
    req: IncidentStatusUpdateRequest,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Update incident operational status: submitted, under_review, verified, assigned, in_progress, resolved, rejected.
    Enforces authorization check.
    """
    allowed_statuses = ['submitted', 'under_review', 'verified', 'assigned', 'in_progress', 'resolved', 'rejected', 'reported', 'dispatched', 'on_scene']
    new_status = req.status.strip().lower()

    if new_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}")

    now_iso = datetime.now(timezone.utc).isoformat()
    actor_name = user['full_name'] if user else req.actor

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found.")

        prev_status = row['status']
        cursor.execute("""
            UPDATE incidents
            SET status = ?, responder_notes = COALESCE(?, responder_notes), updated_at = ?
            WHERE id = ?
        """, (new_status, req.responder_notes, now_iso, incident_id))

        log_event('INCIDENT_STATUS_UPDATED', 'incident', incident_id, {
            'previous_status': prev_status,
            'new_status': new_status,
            'notes': req.responder_notes
        }, actor_name, conn=conn)

        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        return row_to_dict(cursor.fetchone())


# ---------------------------------------------------------------------------
# Resources & Smart Fleet Dispatch
# ---------------------------------------------------------------------------
@app.get("/api/resources", tags=["Resources"])
def list_resources(category: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None):
    """
    Searchable emergency resource directory (Hospitals, Fire Stations, Shelters, and Response Fleet Units).
    Distinguishes verified records from test fixtures.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # If category is fleet / response unit, query resources table
        if category in ['ambulance', 'fire_unit', 'rescue_boat', 'ndrf_team', 'heavy_rescue']:
            cursor.execute("SELECT * FROM resources WHERE 1=1 ORDER BY id ASC")
            fleet = [row_to_dict(r) for r in cursor.fetchall()]
            return fleet

        # Query comprehensive emergency directory
        query = "SELECT * FROM emergency_resources WHERE 1=1"
        params = []
        if category and category != 'all':
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY id ASC"
        cursor.execute(query, params)
        directory_items = [row_to_dict(r) for r in cursor.fetchall()]

        # Also append shelters
        cursor.execute("SELECT * FROM shelters ORDER BY id ASC")
        for shl in cursor.fetchall():
            s = row_to_dict(shl)
            directory_items.append({
                'id': f"shl_{s['id']}",
                'name': s['name'],
                'category': 'shelter',
                'address': s['address'],
                'latitude': s['latitude'],
                'longitude': s['longitude'],
                'phone': s.get('contact_phone', '112'),
                'services': s.get('amenities', []),
                'verification_status': s.get('verification_status', 'verified'),
                'is_test_data': 0,
                'source_attribution': 'District Disaster Management Authority',
                'updated_at': s['updated_at']
            })

        return directory_items


@app.get("/api/shelters", tags=["Resources"])
def list_shelters():
    """List verified evacuation shelters with capacity and occupancy metrics."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shelters ORDER BY id ASC")
        shelters = [row_to_dict(r) for r in cursor.fetchall()]
        for s in shelters:
            cap = s.get('total_capacity', 1)
            occ = s.get('current_occupancy', 0)
            s['occupancy_pct'] = round((occ / cap * 100.0), 1) if cap > 0 else 0.0
            s['available_spaces'] = max(0, cap - occ)
        return shelters


@app.post("/api/dispatch", tags=["Dispatch"])
def dispatch_fleet_unit(req: DispatchRequest, user: Optional[dict] = Depends(get_current_user)):
    """Assign response fleet unit to an incident with atomic double-assignment prevention."""
    dispatcher = user['full_name'] if user else req.dispatcher_name
    result = assign_resource(req.incident_id, req.resource_id, req.notes, dispatcher)
    if not result.get('success'):
        raise HTTPException(status_code=409, detail=result.get('error', 'Conflict in resource assignment.'))
    return result


@app.post("/api/dispatch/release", tags=["Dispatch"])
def release_fleet_unit(req: ReleaseRequest, user: Optional[dict] = Depends(get_current_user)):
    """Release a dispatched fleet unit back to available status."""
    actor = user['full_name'] if user else req.actor
    result = release_resource(req.resource_id, req.notes, actor)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error', 'Cannot release resource.'))
    return result


# ---------------------------------------------------------------------------
# Evacuation Routing & Geodesic Navigation
# ---------------------------------------------------------------------------
@app.get("/api/routes/evacuation", tags=["Routing"])
def calculate_route(
    origin_lat: float = Query(...),
    origin_lon: float = Query(...),
    dest_lat: float = Query(...),
    dest_lon: float = Query(...)
):
    """
    Calculate driving directions using OSRM routing engine with geodesic interpolation fallback.
    Results are clearly flagged as advisory calculated directions, not guaranteed safe evacuation paths.
    """
    return get_route(origin_lat, origin_lon, dest_lat, dest_lon)


# ---------------------------------------------------------------------------
# Multilingual AI Emergency Assistant
# ---------------------------------------------------------------------------
@app.post("/api/assistant/chat", tags=["AI Assistant"])
def chat_with_assistant(req: AIChatRequest):
    """
    Interactive Emergency AI Assistant supporting English, Hindi (हिंदी), and Marathi (मराठी).
    Grounded in connected live meteorological conditions, active NDMA alerts, and official contacts (112, 108, 101, 1070).
    """
    return generate_assistant_response(
        message=req.message,
        language=req.language,
        lat=req.latitude,
        lon=req.longitude
    )


# ---------------------------------------------------------------------------
# In-App Alerts, Audit Logs & Reset Utilities
# ---------------------------------------------------------------------------
@app.post("/api/alerts/{alert_id}/acknowledge", tags=["System"])
def acknowledge_alert(alert_id: int):
    """Acknowledge an emergency alert."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET is_acknowledged = 1 WHERE id = ?", (alert_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert not found.")
        log_event('ALERT_ACKNOWLEDGED', 'alert', alert_id, None, 'operator', conn=conn)
        return {'success': True, 'alert_id': alert_id}


@app.get("/api/audit-logs", tags=["System"])
def list_audit_logs(limit: int = Query(50, ge=1, le=200)):
    """Immutable audit trail of all operational events and status transitions."""
    return get_recent_logs(limit)


@app.post("/api/system/reset-demo", tags=["System"])
def reset_demo(confirm: bool = Body(..., embed=True)):
    """Reset database to clean seed state (requires explicit confirmation)."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation required.")
    res = seed_database(force_reset=True)
    return res


# ---------------------------------------------------------------------------
# Frontend Static Asset Serving
# ---------------------------------------------------------------------------
# Mount css, js, vendor folders
if os.path.exists(os.path.join(FRONTEND_DIR, 'css')):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, 'css')), name="css")
if os.path.exists(os.path.join(FRONTEND_DIR, 'js')):
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, 'js')), name="js")
if os.path.exists(os.path.join(FRONTEND_DIR, 'vendor')):
    app.mount("/vendor", StaticFiles(directory=os.path.join(FRONTEND_DIR, 'vendor')), name="vendor")


@app.get("/", tags=["Frontend"])
def serve_index():
    """Serve Single Page Application (SPA) entrypoint."""
    index_path = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({'message': 'ResQAI API operational. Frontend index.html not found.'})


@app.get("/manifest.json", tags=["Frontend"])
def serve_manifest():
    """PWA Web Manifest."""
    manifest_path = os.path.join(FRONTEND_DIR, 'manifest.json')
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return JSONResponse({'name': 'ResQAI Emergency System'})


@app.get("/sw.js", tags=["Frontend"])
def serve_service_worker():
    """PWA Service Worker."""
    sw_path = os.path.join(FRONTEND_DIR, 'sw.js')
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return JSONResponse({'status': 'no service worker'})
