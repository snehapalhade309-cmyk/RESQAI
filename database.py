"""
ResQAI - Database Layer (SQLite)
Provides thread-safe connection pooling, schema initialization, migrations,
and transactional operations for the full disaster management system.
"""

import sqlite3
import os
import json
from contextlib import contextmanager

# Ensure data directory exists
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'resqai.db')


def get_connection():
    """Create a new SQLite connection with foreign keys and WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")  # High concurrency write-ahead logging
    return conn


@contextmanager
def get_db():
    """Context manager for database connections with automatic commit/rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def _ensure_columns(cursor, table_name, columns_to_add):
    """Safely add missing columns to an existing SQLite table."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    existing_cols = {row['name'] for row in cursor.fetchall()}
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};")


def init_db():
    """Initialize database tables, missing columns, and indexes."""
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Users Table (Authentication & RBAC: citizen, responder, admin)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'citizen',
            full_name TEXT NOT NULL,
            organization TEXT,
            phone TEXT,
            created_at TEXT NOT NULL
        );
        ''')

        # 2. Incidents Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_code TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            location_name TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            reported_severity TEXT NOT NULL,
            affected_people INTEGER DEFAULT 0,
            vulnerability_tags TEXT DEFAULT '[]',
            description TEXT,
            reporter_name TEXT,
            reporter_contact TEXT,
            tracking_pin TEXT,
            calculated_risk_score REAL DEFAULT 0.0,
            risk_category TEXT DEFAULT 'Low',
            risk_factors_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'submitted',
            assigned_unit_id INTEGER NULL,
            responder_notes TEXT,
            image_url TEXT,
            is_demo INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(assigned_unit_id) REFERENCES resources(id) ON DELETE SET NULL
        );
        ''')

        # Migrate existing incidents table if missing new columns
        _ensure_columns(cursor, 'incidents', {
            'tracking_pin': "TEXT DEFAULT 'PIN-1000'",
            'assigned_unit_id': "INTEGER NULL",
            'responder_notes': "TEXT",
            'image_url': "TEXT"
        })

        # 3. Resources Table (Emergency Fleet Units)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            capabilities TEXT DEFAULT '[]',
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            base_station TEXT NOT NULL,
            status TEXT DEFAULT 'available',
            assigned_incident_id INTEGER NULL,
            last_status_update TEXT NOT NULL,
            is_simulated INTEGER DEFAULT 1,
            FOREIGN KEY(assigned_incident_id) REFERENCES incidents(id) ON DELETE SET NULL
        );
        ''')

        # 4. Shelters Table (Evacuation Shelters)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shelters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shelter_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT NOT NULL,
            total_capacity INTEGER NOT NULL,
            current_occupancy INTEGER DEFAULT 0,
            amenities TEXT DEFAULT '[]',
            verification_status TEXT DEFAULT 'verified',
            contact_phone TEXT,
            updated_at TEXT NOT NULL
        );
        ''')

        # 5. Emergency Resources Directory (Hospitals, Fire Stations, Relief Hubs, Police)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            address TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            phone TEXT NOT NULL,
            services TEXT DEFAULT '[]',
            verification_status TEXT DEFAULT 'verified',
            is_test_data INTEGER DEFAULT 0,
            source_attribution TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        ''')

        # 6. Dispatches Table (Atomic Fleet Missions)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dispatches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            resource_id INTEGER NOT NULL,
            dispatch_time TEXT NOT NULL,
            arrival_time TEXT,
            resolution_time TEXT,
            status TEXT DEFAULT 'dispatched',
            notes TEXT,
            dispatched_by TEXT DEFAULT 'ResQAI Dispatcher',
            FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
            FOREIGN KEY(resource_id) REFERENCES resources(id) ON DELETE CASCADE
        );
        ''')

        # 7. Alerts Table (In-App Hazard & NDMA Alerts)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT NOT NULL,
            incident_id INTEGER NULL,
            source TEXT NOT NULL,
            source_url TEXT,
            is_acknowledged INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(incident_id) REFERENCES incidents(id) ON DELETE SET NULL
        );
        ''')

        _ensure_columns(cursor, 'alerts', {
            'source_url': "TEXT"
        })

        # 8. Audit Logs Table (Immutable Operational Activity)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            timestamp TEXT NOT NULL,
            actor TEXT DEFAULT 'operator'
        );
        ''')

        # 9. Disaster Events Cache (Normalized external events from USGS, NDMA, NASA)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS disaster_events (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            event_time TEXT NOT NULL,
            retrieval_time TEXT NOT NULL,
            source_url TEXT,
            data_classification TEXT NOT NULL,
            verification_status TEXT DEFAULT 'verified'
        );
        ''')

        # 10. Notifications Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT DEFAULT 'sent',
            sent_at TEXT NOT NULL
        );
        ''')

        # Create indexes for high-speed indexing and filtering
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(type);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_code ON incidents(incident_code);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_risk ON incidents(risk_category);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_resources_status ON resources(status);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(type);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shelters_type ON shelters(type);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_em_res_cat ON emergency_resources(category);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_ack ON alerts(is_acknowledged);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_disaster_time ON disaster_events(event_time);')


def row_to_dict(row):
    """Utility to convert a sqlite3.Row object to a standard Python dictionary."""
    if row is None:
        return None
    d = dict(row)
    # Parse JSON fields if present
    for json_col in ['vulnerability_tags', 'capabilities', 'amenities', 'services']:
        if json_col in d and isinstance(d[json_col], str):
            try:
                d[json_col] = json.loads(d[json_col])
            except Exception:
                d[json_col] = []
    if 'risk_factors_json' in d and isinstance(d['risk_factors_json'], str):
        try:
            d['risk_factors_json'] = json.loads(d['risk_factors_json'])
        except Exception:
            d['risk_factors_json'] = {}
    return d
