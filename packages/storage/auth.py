"""
Authentication and Session Security Module for InsightForge
Implements multi-tenant user authentication, PBKDF2-HMAC-SHA256 password hashing (100,000 rounds),
cryptographic session tokens, and CSRF protection matching PRD §11 and API_SPEC §3.
"""

import os
import hashlib
import secrets
import hmac
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List

from packages.storage.db import get_db_connection, DB_PATH


def init_auth_tables():
    """Ensure database schema has auth columns and sessions table."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Check if password_hash exists in users
    cur.execute("PRAGMA table_info(users)")
    cols = [r["name"] for r in cur.fetchall()]

    if "password_hash" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "password_salt" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")

    # Create sessions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        csrf_token TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Seed default password for existing analyst if not set
    cur.execute("SELECT id, password_hash FROM users WHERE email = 'analyst@insightforge.ai'")
    user_row = cur.fetchone()
    if user_row and not user_row["password_hash"]:
        pw_hash, pw_salt = hash_password("Analyst@2026!")
        cur.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            (pw_hash, pw_salt, user_row["id"]),
        )

    conn.commit()
    conn.close()


def hash_password(password: str) -> Tuple[str, str]:
    """
    Hashes password using PBKDF2-HMAC-SHA256 with 100,000 iterations and a 16-byte random salt.
    Returns (hash_hex, salt_hex).
    """
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return key.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    """Verifies a plaintext password against the stored PBKDF2 hash using constant-time comparison."""
    if not stored_hash or not salt_hex:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(key.hex(), stored_hash)
    except Exception:
        return False


def create_session(user_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None, days_valid: int = 7) -> Dict[str, Any]:
    """Creates a new authenticated session with cryptographically secure tokens."""
    conn = get_db_connection()
    cur = conn.cursor()

    session_id = f"sess-{uuid.uuid4()}"
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_hex(16)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=days_valid)).isoformat().replace("+00:00", "Z")
    now_str = now.isoformat().replace("+00:00", "Z")

    cur.execute(
        """
        INSERT INTO sessions (id, user_id, token, csrf_token, ip_address, user_agent, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, user_id, token, csrf_token, ip_address, user_agent, expires_at, now_str),
    )
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "token": token,
        "csrf_token": csrf_token,
        "expires_at": expires_at,
    }


def authenticate_user(email: str, password: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> Dict[str, Any]:
    """
    Authenticates a user with email and password.
    Returns user profile, active workspace, session tokens, and organization info.
    Raises ValueError on invalid credentials.
    """
    init_auth_tables()
    norm_email = email.strip().lower()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT u.id, u.organization_id, u.email, u.full_name, u.role, u.is_active,
               u.password_hash, u.password_salt, o.name as org_name, o.slug as org_slug
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE LOWER(u.email) = ?
        """,
        (norm_email,),
    )
    user = cur.fetchone()

    if not user:
        conn.close()
        raise ValueError("AUTH_INVALID_CREDENTIALS")

    if not user["is_active"]:
        conn.close()
        raise ValueError("AUTH_ACCOUNT_DISABLED")

    if not verify_password(password, user["password_hash"], user["password_salt"]):
        conn.close()
        raise ValueError("AUTH_INVALID_CREDENTIALS")

    # Fetch default workspace
    cur.execute("SELECT id, name, slug FROM workspaces WHERE organization_id = ? LIMIT 1", (user["organization_id"],))
    ws = cur.fetchone()
    conn.close()

    # Create session
    session_data = create_session(user["id"], ip_address, user_agent)

    # Record login audit event
    record_auth_audit(
        user["organization_id"],
        user["id"],
        "USER_LOGIN",
        {"email": norm_email, "ip_address": ip_address},
        ip_address,
    )

    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
        },
        "organization": {
            "id": user["organization_id"],
            "name": user["org_name"],
            "slug": user["org_slug"],
        },
        "workspace": {
            "id": ws["id"] if ws else None,
            "name": ws["name"] if ws else "Default Workspace",
        },
        "session": session_data,
        "csrf_token": session_data["csrf_token"],
    }


def register_user(
    name: str,
    email: str,
    password: str,
    org_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Registers a new tenant organization, workspace, default project, and user.
    Enforces password quality (minimum 8 characters) and uniqueness.
    """
    init_auth_tables()
    norm_email = email.strip().lower()

    if len(password) < 8:
        raise ValueError("AUTH_WEAK_PASSWORD: Password must be at least 8 characters.")

    conn = get_db_connection()
    cur = conn.cursor()

    # Check email uniqueness
    cur.execute("SELECT id FROM users WHERE LOWER(email) = ?", (norm_email,))
    if cur.fetchone():
        conn.close()
        raise ValueError("AUTH_EMAIL_TAKEN: An account with this email address already exists.")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    org_id = f"org-{uuid.uuid4()}"
    ws_id = f"ws-{uuid.uuid4()}"
    user_id = f"usr-{uuid.uuid4()}"
    proj_id = f"proj-{uuid.uuid4()}"

    company = org_name.strip() if org_name and org_name.strip() else f"{name.strip()}'s Org"
    base_slug = "".join(c if c.isalnum() else "-" for c in company.lower()).strip("-")[:32] or "org"
    slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    pw_hash, pw_salt = hash_password(password)

    try:
        # Insert Organization
        cur.execute(
            "INSERT INTO organizations (id, name, slug, created_at) VALUES (?, ?, ?, ?)",
            (org_id, company, slug, now),
        )
        # Insert Workspace
        cur.execute(
            "INSERT INTO workspaces (id, organization_id, name, slug, created_at) VALUES (?, ?, ?, ?, ?)",
            (ws_id, org_id, "Default Workspace", f"default-workspace-{uuid.uuid4().hex[:4]}", now),
        )
        # Insert User
        cur.execute(
            """
            INSERT INTO users (id, organization_id, email, full_name, password_hash, password_salt, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (user_id, org_id, norm_email, name.strip(), pw_hash, pw_salt, "ADMIN", now),
        )
        # Insert Starter Project
        cur.execute(
            """
            INSERT INTO projects (id, workspace_id, name, domain, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (proj_id, ws_id, "Omnichannel Retail Insights", "retail", "Initial analytics workspace project", now),
        )
        conn.commit()
    finally:
        conn.close()

    session_data = create_session(user_id, ip_address, user_agent)

    record_auth_audit(
        org_id,
        user_id,
        "USER_REGISTER",
        {"email": norm_email, "name": name, "organization": company},
        ip_address,
    )

    return {
        "user": {
            "id": user_id,
            "email": norm_email,
            "full_name": name.strip(),
            "role": "ADMIN",
        },
        "organization": {
            "id": org_id,
            "name": company,
            "slug": slug,
        },
        "workspace": {
            "id": ws_id,
            "name": "Default Workspace",
        },
        "session": session_data,
        "csrf_token": session_data["csrf_token"],
    }


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Validates session token and returns full user, workspace, and organization context."""
    if not token:
        return None

    init_auth_tables()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id as session_id, s.token, s.csrf_token, s.expires_at,
               u.id as user_id, u.email, u.full_name, u.role, u.is_active,
               o.id as org_id, o.name as org_name, o.slug as org_slug
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        JOIN organizations o ON u.organization_id = o.id
        WHERE s.token = ? AND s.expires_at > ?
        """,
        (token, now),
    )
    row = cur.fetchone()
    if not row or not row["is_active"]:
        conn.close()
        return None

    # Fetch workspace
    cur.execute("SELECT id, name FROM workspaces WHERE organization_id = ? LIMIT 1", (row["org_id"],))
    ws = cur.fetchone()
    conn.close()

    return {
        "user": {
            "id": row["user_id"],
            "email": row["email"],
            "full_name": row["full_name"],
            "role": row["role"],
        },
        "organization": {
            "id": row["org_id"],
            "name": row["org_name"],
            "slug": row["org_slug"],
        },
        "workspace": {
            "id": ws["id"] if ws else None,
            "name": ws["name"] if ws else "Default Workspace",
        },
        "session_id": row["session_id"],
        "csrf_token": row["csrf_token"],
    }


def revoke_session(token: str) -> bool:
    """Revokes a single session token (logout)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def revoke_all_sessions(user_id: str) -> bool:
    """Revokes all sessions for a user (security reset / logout all)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def record_auth_audit(org_id: str, user_id: str, event_type: str, details: Dict[str, Any], ip_address: Optional[str] = None):
    """Inserts record into audit_events table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        event_id = f"aud-{uuid.uuid4()}"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        import json
        cur.execute(
            """
            INSERT INTO audit_events (id, organization_id, user_id, event_type, resource_type, resource_id, details_json, ip_address, created_at)
            VALUES (?, ?, ?, ?, 'USER', ?, ?, ?, ?)
            """,
            (event_id, org_id, user_id, event_type, user_id, json.dumps(details), ip_address, now),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
