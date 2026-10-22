"""
ResQAI - Realistic Emergency Demonstration Seed Data
Populates SQLite database with structured incidents, simulated rescue fleet,
evacuation shelters, verified emergency resource directory, and authenticated user roles.
"""

import os
import sys
from datetime import datetime, timezone
import json
import bcrypt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import get_db, init_db
from backend.risk_engine import calculate_risk
from backend.audit_service import log_event


def hash_pw(plain: str) -> str:
    """Helper to bcrypt hash passwords."""
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(plain.encode('utf-8'), salt).decode('utf-8')


def seed_database(force_reset=False):
    """Populate database with initial emergency management dataset."""
    init_db()

    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        cursor = conn.cursor()

        # Check if already seeded
        cursor.execute("SELECT COUNT(*) as count FROM incidents")
        count = cursor.fetchone()['count']
        if count > 0 and not force_reset:
            return {'message': 'Database already contains data. Skipped seeding.', 'seeded': False}

        if force_reset:
            cursor.execute("DELETE FROM dispatches")
            cursor.execute("DELETE FROM alerts")
            cursor.execute("DELETE FROM audit_logs")
            cursor.execute("DELETE FROM resources")
            cursor.execute("DELETE FROM shelters")
            cursor.execute("DELETE FROM emergency_resources")
            cursor.execute("DELETE FROM incidents")
            cursor.execute("DELETE FROM users")
            cursor.execute("DELETE FROM notifications")
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('incidents', 'resources', 'shelters', 'dispatches', 'alerts', 'audit_logs', 'users', 'emergency_resources', 'notifications')")
            except Exception:
                pass

        # 0. Seed Users (Admin, Responder, Citizen)
        users_data = [
            (
                'admin', 'commander@resqai.org', hash_pw('admin123'), 'admin',
                'Col. Rajesh Malhotra (Retd.)', 'State Disaster Management Control Room', '+91-20-2612-8000', now_iso
            ),
            (
                'responder', 'responder.alpha@ndrf.gov.in', hash_pw('responder123'), 'responder',
                'Inspector Amit Kulkarni', '5th Battalion NDRF Search & Rescue', '+91-98220-11223', now_iso
            ),
            (
                'citizen', 'pooja.deshmukh@gmail.com', hash_pw('citizen123'), 'citizen',
                'Pooja Deshmukh', 'Civilian Citizen', '+91-98220-55667', now_iso
            )
        ]

        cursor.executemany("""
            INSERT INTO users (
                username, email, password_hash, role, full_name, organization, phone, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, users_data)

        # 1. Seed Shelters
        shelters_data = [
            (
                'SHL-01', 'Balewadi Sports Complex Evacuation Center', 'stadium',
                18.5775, 73.7583, 'Balewadi Stadium Road, Pune', 1500, 320,
                json.dumps(['medical', 'food', 'power_backup', 'clean_water', 'wheelchair_accessible']),
                'verified', '+91-20-2569-8001', now_iso
            ),
            (
                'SHL-02', 'Shivajinagar College Gymnasium Emergency Shelter', 'school',
                18.5284, 73.8567, 'Wellesley Road, Shivajinagar, Pune', 800, 160,
                json.dumps(['medical', 'food', 'power_backup', 'clean_water']),
                'verified', '+91-20-2569-8002', now_iso
            ),
            (
                'SHL-03', 'Hadapsar Municipal High-Ground Relief Center', 'community_center',
                18.5050, 73.9310, 'Gadital High Ground, Hadapsar, Pune', 600, 85,
                json.dumps(['food', 'clean_water', 'power_backup']),
                'verified', '+91-20-2569-8003', now_iso
            ),
            (
                'SHL-04', 'Kothrud Community Relief Camp', 'relief_camp',
                18.5020, 73.8040, 'Near Karve Statue, Kothrud, Pune', 450, 210,
                json.dumps(['medical', 'clean_water', 'wheelchair_accessible']),
                'verified', '+91-20-2569-8004', now_iso
            ),
            (
                'SHL-05', 'Pimpri Civic Administrative Disaster Shelter', 'community_center',
                18.6279, 73.7990, 'Old Mumbai-Pune Highway, Pimpri', 1000, 140,
                json.dumps(['medical', 'food', 'power_backup', 'clean_water', 'wheelchair_accessible']),
                'verified', '+91-20-2569-8005', now_iso
            )
        ]

        cursor.executemany("""
            INSERT INTO shelters (
                shelter_code, name, type, latitude, longitude, address,
                total_capacity, current_occupancy, amenities, verification_status,
                contact_phone, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, shelters_data)

        # 2. Seed Emergency Resources Directory (Hospitals, Fire Stations, NDRF Bases)
        emergency_resources_data = [
            (
                'Sassoon General Hospital & Level-1 Trauma Centre', 'hospital',
                'Station Road, Near Pune Railway Station, Pune 411001', 18.5255, 73.8741,
                '+91-20-2612-8000', json.dumps(['24/7 Trauma Emergency', 'Burn ICU', 'Blood Bank', 'Ambulance Outpost']),
                'verified', 0, 'Government of Maharashtra Health Directorate', now_iso
            ),
            (
                'KEM Hospital & Research Centre', 'hospital',
                '489 Rasta Peth, Sardar Moodliar Road, Pune 411011', 18.5204, 73.8690,
                '+91-20-6603-7300', json.dumps(['Emergency Care', 'Pediatric ICU', 'Oxygen Plant', 'Cardiac Unit']),
                'verified', 0, 'Maharashtra Medical Council Directory', now_iso
            ),
            (
                'Aundh District Hospital & Civil Emergency Center', 'hospital',
                'Sangvi Road, Near Shivaji Chowk, Aundh, Pune 411027', 18.5680, 73.8050,
                '+91-20-2588-4100', json.dumps(['Emergency Casualty', 'General Ward', 'Maternity', 'Infection Isolation']),
                'verified', 0, 'Directorate of Health Services Pune', now_iso
            ),
            (
                'Pune Municipal Central Fire Brigade Headquarters', 'fire_station',
                'Dr. Ambedkar Road, Shivajinagar, Pune 411005', 18.5300, 73.8480,
                '+91-20-2550-6101', json.dumps(['Hydraulic Platform', 'Foam Tenders', 'Water Bowsers', 'Heavy Extrication']),
                'verified', 0, 'Pune Municipal Corporation Fire Department', now_iso
            ),
            (
                'Kothrud Fire Substation & Emergency Rescue Hub', 'fire_station',
                'Near Karve Road Flyover, Kothrud, Pune 411038', 18.5020, 73.8040,
                '+91-20-2544-2101', json.dumps(['First Responder Tender', 'Breathing Apparatus Support', 'Tree Cutting']),
                'verified', 0, 'PMC Fire Department', now_iso
            ),
            (
                '5th Battalion NDRF (National Disaster Response Force) Base', 'ndrf_base',
                'Sudumbare Post, Talegaon-Chakan Road, Pune 410507', 18.7180, 73.6800,
                '+91-2114-247000', json.dumps(['Search & Rescue Canine', 'Inflatable Boats', 'Collapse Structure Search', 'Hazmat CBRN Unit']),
                'verified', 0, 'Ministry of Home Affairs (MHA), India', now_iso
            ),
            (
                'Pune District Emergency Operations Centre (DEOC)', 'command_center',
                'Collector Office Compound, Bund Garden Road, Pune 411001', 18.5240, 73.8780,
                '+91-20-2612-3371', json.dumps(['Disaster Helpline 1077', 'Satellite Comms', 'Tactical Dispatch Net', 'Flood Gauge Telemetry']),
                'verified', 0, 'District Disaster Management Authority (DDMA)', now_iso
            )
        ]

        cursor.executemany("""
            INSERT INTO emergency_resources (
                name, category, address, latitude, longitude, phone,
                services, verification_status, is_test_data, source_attribution, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, emergency_resources_data)

        # 3. Seed Resources (Simulated Fleet Units)
        resources_data = [
            (
                'RES-AMB-01', 'ALS Trauma Ambulance 01', 'ambulance',
                json.dumps(['als', 'first_aid', 'trauma', 'oxygen']),
                18.5284, 73.8439, 'Sassoon General Hospital Outpost', 'available', None, now_iso, 1
            ),
            (
                'RES-AMB-02', 'BLS Rapid Response Ambulance 02', 'ambulance',
                json.dumps(['bls', 'first_aid', 'patient_transport']),
                18.5912, 73.7820, 'Aundh District Hospital', 'available', None, now_iso, 1
            ),
            (
                'RES-AMB-03', 'Mobile Intensive Care Ambulance 03', 'ambulance',
                json.dumps(['als', 'pediatric', 'ventilator', 'oxygen']),
                18.5020, 73.8150, 'Kothrud Medical Station', 'available', None, now_iso, 1
            ),
            (
                'RES-FIR-01', 'Heavy Water Tender Unit 101', 'fire_unit',
                json.dumps(['firefighting', 'water_tender', 'foam_discharge']),
                18.5300, 73.8480, 'Shivajinagar Central Fire HQ', 'available', None, now_iso, 1
            ),
            (
                'RES-FIR-02', 'Industrial Hazmat Foam Unit 102', 'fire_unit',
                json.dumps(['firefighting', 'hazmat', 'gas_containment']),
                18.6320, 73.8310, 'Bhosari MIDC Fire Depot', 'available', None, now_iso, 1
            ),
            (
                'RES-BOT-01', 'Gemini Inflatable Flood Rescue Craft 201', 'rescue_boat',
                json.dumps(['water_rescue', 'evacuation', 'shallow_draft']),
                18.5240, 73.8720, 'Yerawada Riverbank Outpost', 'available', None, now_iso, 1
            ),
            (
                'RES-BOT-02', 'Tactical Motorized Swiftwater Boat 202', 'rescue_boat',
                json.dumps(['water_rescue', 'night_search', 'swiftwater']),
                18.5080, 73.8340, 'Sinhagad River Logistics Depot', 'available', None, now_iso, 1
            ),
            (
                'RES-NDR-01', 'NDRF Battalion Alpha Search Team', 'ndrf_team',
                json.dumps(['search_and_rescue', 'structural_collapse', 'k9', 'water_rescue']),
                18.5750, 73.8690, 'Khadki Disaster Command HQ', 'available', None, now_iso, 1
            ),
            (
                'RES-NDR-02', 'NDRF Quick Response Team Bravo', 'ndrf_team',
                json.dumps(['search_and_rescue', 'debris_clearing', 'first_aid']),
                18.5150, 73.7920, 'Warje Emergency Reserve Hub', 'available', None, now_iso, 1
            ),
            (
                'RES-HVY-01', 'Heavy Extrication & Debris Crane 301', 'heavy_rescue',
                json.dumps(['extrication', 'heavy_machinery', 'concrete_cutting']),
                18.4900, 73.8700, 'Swargate Civil Engineering Yard', 'available', None, now_iso, 1
            )
        ]

        cursor.executemany("""
            INSERT INTO resources (
                resource_code, name, type, capabilities, latitude, longitude,
                base_station, status, assigned_incident_id, last_status_update, is_simulated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, resources_data)

        # 4. Seed Incidents with Calculated Risk
        raw_incidents = [
            {
                'incident_code': 'INC-2026-001',
                'tracking_pin': 'PIN-1001',
                'type': 'flood',
                'title': 'Mula River Flash Inundation & Bank Overflow',
                'location_name': 'Sangamwadi Bridge Lowlands, Pune',
                'latitude': 18.5312,
                'longitude': 73.8682,
                'reported_severity': 'severe',
                'affected_people': 42,
                'vulnerability_tags': ['elderly', 'trapped', 'mobility_impaired'],
                'description': 'Rapidly rising water levels due to dam discharge upstream. Multiple single-story homes flooded with 4-5 feet of standing water. Several elderly residents unable to self-evacuate.',
                'reporter_name': 'Anand Verma (Ward Officer)',
                'reporter_contact': '+91-98220-11223',
                'status': 'verified',
                'is_demo': 1
            },
            {
                'incident_code': 'INC-2026-002',
                'tracking_pin': 'PIN-1002',
                'type': 'landslide',
                'title': 'Katraj Ghat Ridge Mudslide & Road Blockage',
                'location_name': 'Katraj Tunnel Bypass Corridor',
                'latitude': 18.4485,
                'longitude': 73.8589,
                'reported_severity': 'severe',
                'affected_people': 15,
                'vulnerability_tags': ['trapped'],
                'description': 'Heavy hillside slope failure deposited boulder debris across both lanes. Two passenger vehicles partially trapped in embankment mud.',
                'reporter_name': 'Highway Patrol Unit 4',
                'reporter_contact': '+91-98220-44556',
                'status': 'under_review',
                'is_demo': 1
            },
            {
                'incident_code': 'INC-2026-003',
                'tracking_pin': 'PIN-1003',
                'type': 'fire',
                'title': 'Industrial Chemical Warehouse Blaze',
                'location_name': 'Bhosari MIDC Industrial Zone',
                'latitude': 18.6280,
                'longitude': 73.8420,
                'reported_severity': 'catastrophic',
                'affected_people': 28,
                'vulnerability_tags': ['medical_equipment'],
                'description': 'Explosive drum rupture in solvent storage unit. Thick toxic plume moving south-west. Factory floor evacuated but adjacent clinic reports vulnerable patients.',
                'reporter_name': 'Security Chief R. Shinde',
                'reporter_contact': '+91-98220-77889',
                'status': 'submitted',
                'is_demo': 1
            },
            {
                'incident_code': 'INC-2026-004',
                'tracking_pin': 'PIN-1004',
                'type': 'accident',
                'title': 'Multi-Vehicle Collision with Fuel Leakage',
                'location_name': 'Wakad Highway Flyover Ramp',
                'latitude': 18.5987,
                'longitude': 73.7663,
                'reported_severity': 'moderate',
                'affected_people': 8,
                'vulnerability_tags': ['children'],
                'description': 'Collision involving mini-bus and cargo truck in rainy conditions. Fuel spill on asphalt; 3 injured passengers require immediate hospital transfer.',
                'reporter_name': 'Traffic Warden D. Patil',
                'reporter_contact': '+91-98220-99001',
                'status': 'submitted',
                'is_demo': 1
            },
            {
                'incident_code': 'INC-2026-005',
                'tracking_pin': 'PIN-1005',
                'type': 'severe_weather',
                'title': 'Gale Storm Tree Fall on Overhead Transit Wire',
                'location_name': 'Shivajinagar Bus Station Terminal',
                'latitude': 18.5314,
                'longitude': 73.8446,
                'reported_severity': 'minor',
                'affected_people': 4,
                'vulnerability_tags': ['elderly'],
                'description': 'High wind gusts snapped large banyan tree limb onto electric distribution cables. Minor burns reported; traffic transit halted.',
                'reporter_name': 'Station Master Joshi',
                'reporter_contact': '+91-98220-33445',
                'status': 'submitted',
                'is_demo': 1
            }
        ]

        for item in raw_incidents:
            risk = calculate_risk(item, weather_data={'precipitation': 18.0, 'wind_speed': 25.0, 'temperature': 24.0})

            cursor.execute("""
                INSERT INTO incidents (
                    incident_code, type, title, location_name, latitude, longitude,
                    reported_severity, affected_people, vulnerability_tags, description,
                    reporter_name, reporter_contact, tracking_pin, calculated_risk_score, risk_category,
                    risk_factors_json, status, is_demo, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item['incident_code'], item['type'], item['title'], item['location_name'],
                item['latitude'], item['longitude'], item['reported_severity'], item['affected_people'],
                json.dumps(item['vulnerability_tags']), item['description'], item['reporter_name'],
                item['reporter_contact'], item['tracking_pin'], risk['score'], risk['category'],
                json.dumps(risk['factor_breakdown']), item['status'], item['is_demo'],
                now_iso, now_iso
            ))

        # 5. Seed Alerts
        cursor.execute("SELECT id FROM incidents WHERE incident_code = 'INC-2026-001'")
        inc1_row = cursor.fetchone()
        inc1_id = inc1_row['id'] if inc1_row else None

        cursor.execute("SELECT id FROM incidents WHERE incident_code = 'INC-2026-003'")
        inc3_row = cursor.fetchone()
        inc3_id = inc3_row['id'] if inc3_row else None

        alerts_data = [
            (
                'CRITICAL: Flash Flood Evacuation Priority',
                'Mula River overflow at Sangamwadi Bridge (INC-2026-001). Risk Score 88.0. Watercraft & boat rescue mobilization advised.',
                'critical', inc1_id, 'Risk Intelligence Engine', 'https://sachet.ndma.gov.in/', 0, now_iso
            ),
            (
                'HIGH SEVERITY: Chemical Fire Plume Alert',
                'Hazardous smoke plume at Bhosari MIDC (INC-2026-003). Hazmat containment units & downwind air safety perimeter requested.',
                'critical', inc3_id, 'Risk Intelligence Engine', 'https://sachet.ndma.gov.in/', 0, now_iso
            ),
            (
                'WEATHER ADVISORY: Heavy Monsoon Rain Band',
                'Localized precipitation forecast exceeding 20 mm/hr in river basin zones. Maintain heightened alert status.',
                'warning', None, 'Open-Meteo Weather Integration', 'https://open-meteo.com/', 0, now_iso
            )
        ]

        cursor.executemany("""
            INSERT INTO alerts (
                title, message, severity, incident_id, source, source_url, is_acknowledged, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, alerts_data)

        # 6. Log audit event
        log_event('DATABASE_SEEDED', 'system', None, {
            'users': len(users_data),
            'incidents': len(raw_incidents),
            'resources': len(resources_data),
            'shelters': len(shelters_data),
            'emergency_directory': len(emergency_resources_data)
        }, 'system', conn=conn)

    return {'message': 'Database successfully seeded with realistic emergency dataset and authenticated users.', 'seeded': True}


if __name__ == '__main__':
    res = seed_database(force_reset=True)
    print(res)
