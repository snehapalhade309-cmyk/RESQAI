"""
ResQAI - Role-Based Authentication & Authorization (RBAC)
Provides secure password hashing (bcrypt), JSON Web Token (JWT) issuing/verification,
and FastAPI security dependencies for Citizens, Responders, and Administrators.
"""

import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.database import get_db, row_to_dict

# Configuration from environment variables
JWT_SECRET_KEY = os.environ.get("RESQAI_JWT_SECRET", "resqai-super-secret-key-emergency-command-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security_bearer = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Hash password using bcrypt with salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT bearer token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate JWT bearer token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> Optional[dict]:
    """
    FastAPI dependency: Extract authenticated user from Authorization header.
    Returns user dict or None if unauthenticated.
    """
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    username = payload["sub"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, role, full_name, organization, phone, created_at FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            return None
        return row_to_dict(user_row)


def require_authenticated_user(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """FastAPI dependency: Requires any authenticated user (citizen, responder, admin)."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(allowed_roles: List[str]):
    """FastAPI dependency factory: Enforces specific roles (e.g. ['responder', 'admin'])."""
    def role_checker(user: Optional[dict] = Depends(get_current_user)) -> dict:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_role = user.get("role", "citizen")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {user_role}",
            )
        return user
    return role_checker
