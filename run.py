"""
ResQAI - AI-Powered Emergency Management & Response System
Command Center Application Runner
Entry point to launch the complete full-stack emergency response platform with FastAPI.
"""

import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import init_db
from backend.seed_data import seed_database


def main():
    print("=" * 75)
    print("  RESQAI — AI-POWERED EMERGENCY MANAGEMENT & RESPONSE SYSTEM")
    print("  Tagline: Detect Faster. Respond Smarter. Save Lives.")
    print("=" * 75)

    # 1. Initialize SQLite Database Schema
    print("[1/3] Initializing SQLite database schema...")
    init_db()

    # 2. Seed Realistic Scenario Dataset if Empty
    print("[2/3] Checking dataset status...")
    seed_res = seed_database(force_reset=False)
    if seed_res.get('seeded'):
        print("      -> Initial emergency dataset and accounts seeded.")
    else:
        print("      -> Existing database verified.")

    # 3. Launch FastAPI ASGI Server with Uvicorn
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    print(f"[3/3] Launching FastAPI REST API on http://{host}:{port}")
    print("=" * 75)
    print(f"  COMMAND CENTER READY: Open your browser at http://{host}:{port}")
    print(f"  INTERACTIVE API DOCS: Open Swagger UI at http://{host}:{port}/docs")
    print(f"  REDOC SPECIFICATION : Open ReDoc at http://{host}:{port}/redoc")
    print("  Default Accounts:")
    print("    - Admin:     username 'admin'     | password 'admin123'")
    print("    - Responder: username 'responder' | password 'responder123'")
    print("    - Citizen:   username 'citizen'   | password 'citizen123'")
    print("  Press Ctrl+C to terminate.")
    print("=" * 75)

    try:
        import uvicorn
        uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")
    except ImportError:
        print("Uvicorn not found, falling back to Flask...")
        from backend.app import app
        app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()
