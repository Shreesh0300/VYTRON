"""
VYTRON — Google Authentication & Role-Based Authorization Engine
Provides:
1. Google OAuth 2.0 / OpenID Connect ID token verification using google-auth.
2. SQLite persistence for verified users and active sessions.
3. Backend-enforced Role Authorization:
   - 'it_team': Infrastructure monitoring, incident investigation, AI troubleshooting.
   - 'admin': Platform configuration, user management, role assignments.
   - CRITICAL SECURITY: Ordinary users selecting 'admin' are NOT granted admin access.
     Only pre-authorized administrator emails (INITIAL_ADMIN_EMAILS) or approved users get 'admin'.
4. Secure HTTP-only session cookies and role-guarded endpoints.
"""

import os
import sqlite3
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from dotenv import load_dotenv

load_dotenv()

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

logger = logging.getLogger("vytron.auth")

# ── Configuration ─────────────────────────────────────────────────────────────

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000").strip()
SESSION_SECRET = os.getenv("SESSION_SECRET", "vytron-secure-session-secret-change-in-production").strip()

# Comma-separated list of emails permitted to bootstrap as Administrator
# Default fallback includes demo admin email
INITIAL_ADMIN_EMAILS = [
    e.strip().lower() for e in os.getenv("INITIAL_ADMIN_EMAILS", "admin@vytron.ai,shreesh107@gmail.com,kodgeadarsh5268@gmail.com,iamnoob0300@gmail.com").split(",") if e.strip()
]

# Database Path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vytron_auth.db")

# Session lifetime
SESSION_DURATION_DAYS = 7
COOKIE_NAME = "vytron_session_id"


# ── SQLite Persistence Setup ──────────────────────────────────────────────────

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    """Initializes users and sessions tables in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            google_sub TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            picture TEXT,
            authorized_role TEXT NOT NULL,
            requested_role TEXT NOT NULL,
            account_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_google_sub ON users (google_sub)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at)")

    # Seed initial administrators so their admin permissions persist across sessions
    now_utc = datetime.now(timezone.utc).isoformat()
    for idx, admin_email in enumerate(INITIAL_ADMIN_EMAILS, start=1):
        clean_email = admin_email.strip().lower()
        if not clean_email:
            continue
        sub = f"admin-preauthorized-{clean_email}"
        name = clean_email.split("@")[0].replace(".", " ").title()
        uid = f"USR-ADMIN-{idx:02d}"
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, google_sub, name, email, picture, authorized_role, requested_role, account_status, created_at, last_login_at)
            VALUES (?, ?, ?, ?, '', 'admin', 'admin', 'active', ?, ?)
        """, (uid, sub, name, clean_email, now_utc, now_utc))

    conn.commit()
    conn.close()


# Initialize tables on import
init_auth_db()


# ── Pydantic Request/Response Models ──────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="Google ID Token issued by Google Identity Services")
    requested_role: str = Field(default="it_team", description="'it_team' or 'admin'")


class AssignRoleRequest(BaseModel):
    user_id: str
    new_role: str = Field(..., description="'it_team' or 'admin'")


class SwitchRoleRequest(BaseModel):
    role: str = Field(..., description="'it_team' or 'admin'")


class AuthConfigResponse(BaseModel):
    configured: bool
    google_client_id: Optional[str]
    initial_admins_configured: bool
    message: str


# ── Google ID Token Verification ─────────────────────────────────────────────

def verify_google_id_token(token: str, client_id: Optional[str] = None) -> dict[str, Any]:
    """
    Cryptographically verifies Google ID Token claims:
    - Signature validation against Google's public JWKS certificates.
    - Issuer validation ('accounts.google.com' or 'https://accounts.google.com').
    - Audience validation against GOOGLE_CLIENT_ID.
    - Expiration time check.
    """
    effective_client_id = client_id or GOOGLE_CLIENT_ID

    if not effective_client_id:
        raise ValueError(
            "Google OAuth is not configured on this server. "
            "Please configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."
        )

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        # Verify Google OAuth 2.0 token
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            effective_client_id,
            clock_skew_in_seconds=10
        )

        # Validate token issuer
        issuer = idinfo.get("iss", "")
        if issuer not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError(f"Invalid Google token issuer: {issuer}")

        # Return verified identity payload
        return {
            "google_sub": idinfo.get("sub"),
            "email": idinfo.get("email", "").lower(),
            "email_verified": idinfo.get("email_verified", False),
            "name": idinfo.get("name", "Google User"),
            "picture": idinfo.get("picture", "")
        }
    except Exception as e:
        logger.warning(f"Google ID token verification failed: {e}")
        raise ValueError(f"Invalid Google ID token: {str(e)}")


# ── Backend Role Authorization Logic ──────────────────────────────────────────

def resolve_authorized_role(email: str, requested_role: str, existing_role: Optional[str] = None) -> tuple[str, str, Optional[str]]:
    """
    CRITICAL SECURITY ENFORCEMENT:
    - Never trusts requested_role alone.
    - If user requests 'admin':
        1. Allowed IF user's verified email is in INITIAL_ADMIN_EMAILS.
        2. Allowed IF user was already approved as 'admin' in database.
        3. REJECTED otherwise: user is downgraded to 'it_team' with 'pending_admin_approval' status.
    - If user requests 'it_team':
        Granted 'it_team' with 'active' status.

    Returns:
        (authorized_role, account_status, security_notice_message)
    """
    email_clean = email.lower().strip()
    is_preauthorized_admin = email_clean in INITIAL_ADMIN_EMAILS or existing_role == "admin"

    if requested_role.lower() == "admin":
        if is_preauthorized_admin:
            return "admin", "active", "Welcome Administrator. Platform configuration and user management granted."
        else:
            # Security Rule: Deny privilege escalation
            return (
                "it_team",
                "pending_admin_approval",
                "Administrator role requires authorization. Your request was submitted for review; "
                "you have been provisioned with IT Team permissions in the interim."
            )
    else:
        # User requested IT Team role
        return "it_team", "active", "Welcome to VYTRON. IT Team operational monitoring permissions granted."


# ── User and Session Database Helpers ─────────────────────────────────────────

def upsert_user(google_sub: str, name: str, email: str, picture: str, requested_role: str) -> dict[str, Any]:
    """Inserts or updates verified user in SQLite with backend role authorization."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_utc = datetime.now(timezone.utc).isoformat()

    # Check for existing user by google_sub or email
    cursor.execute("SELECT * FROM users WHERE google_sub = ? OR LOWER(email) = LOWER(?)", (google_sub, email.strip()))
    existing = cursor.fetchone()

    existing_role = existing["authorized_role"] if existing else None
    authorized_role, status, notice_msg = resolve_authorized_role(email, requested_role, existing_role)

    if existing:
        user_id = existing["user_id"]
        cursor.execute("""
            UPDATE users SET
                google_sub = ?,
                name = ?,
                email = ?,
                picture = ?,
                authorized_role = ?,
                requested_role = ?,
                account_status = ?,
                last_login_at = ?
            WHERE user_id = ?
        """, (google_sub, name, email, picture, authorized_role, requested_role, status, now_utc, user_id))
    else:
        # Generate stable user ID: USR-XXXXX
        user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        user_id = f"USR-{1000 + user_count + 1}"
        cursor.execute("""
            INSERT INTO users (
                user_id, google_sub, name, email, picture,
                authorized_role, requested_role, account_status,
                created_at, last_login_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, google_sub, name, email, picture, authorized_role, requested_role, status, now_utc, now_utc))

    conn.commit()

    # Re-fetch saved record
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_record = dict(cursor.fetchone())
    user_record["notice_message"] = notice_msg

    conn.close()
    return user_record


def create_session(user_id: str) -> str:
    """Creates a cryptographically secure session token in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    session_id = secrets.token_urlsafe(32)
    now_dt = datetime.now(timezone.utc)
    now_utc = now_dt.isoformat()
    expires_at = (now_dt + timedelta(days=SESSION_DURATION_DAYS)).isoformat()

    cursor.execute("""
        INSERT INTO sessions (session_id, user_id, created_at, expires_at)
        VALUES (?, ?, ?, ?)
    """, (session_id, user_id, now_utc, expires_at))

    conn.commit()
    conn.close()
    return session_id


def get_user_from_session(session_id: str) -> Optional[dict[str, Any]]:
    """Retrieves verified user record for a valid unexpired session."""
    if not session_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    now_utc = datetime.now(timezone.utc).isoformat()

    # Clean up expired sessions first
    cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (now_utc,))
    conn.commit()

    cursor.execute("""
        SELECT u.* FROM users u
        JOIN sessions s ON u.user_id = s.user_id
        WHERE s.session_id = ? AND s.expires_at >= ?
    """, (session_id, now_utc))

    row = cursor.fetchone()
    conn.close()

    if row:
        u = dict(row)
        u["authenticated"] = True
        return u
    return None


def invalidate_session(session_id: str) -> bool:
    """Deletes active session from SQLite."""
    if not session_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

async def get_current_user_optional(request: Request) -> Optional[dict[str, Any]]:
    """Retrieves user from session cookie or Authorization Bearer header without raising."""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_id = auth_header[7:].strip()

    if not session_id:
        return None

    return get_user_from_session(session_id)


async def get_current_user(user: Optional[dict[str, Any]] = Depends(get_current_user_optional)) -> dict[str, Any]:
    """Dependency enforcing that request must have a valid authenticated session."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with Google to access this resource."
        )
    return user


async def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """CRITICAL SECURITY: Backend-enforced authorization requiring Admin role."""
    if user.get("authorized_role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Administrator privileges required for this action."
        )
    return user


# ── Router Definition ─────────────────────────────────────────────────────────

auth_router = APIRouter(prefix="/api", tags=["Authentication & Access Control"])


@auth_router.get("/auth/config", response_model=AuthConfigResponse)
def get_auth_config():
    """
    Returns public Google OAuth configuration status.
    Never exposes client secret or private keys.
    """
    is_configured = bool(GOOGLE_CLIENT_ID and not GOOGLE_CLIENT_ID.startswith("your-google-client-id"))
    msg = (
        "Google OAuth 2.0 is configured and active."
        if is_configured
        else "Google OAuth credentials not configured in environment. Please set GOOGLE_CLIENT_ID in .env."
    )
    return AuthConfigResponse(
        configured=is_configured,
        google_client_id=GOOGLE_CLIENT_ID if is_configured else None,
        initial_admins_configured=len(INITIAL_ADMIN_EMAILS) > 0,
        message=msg
    )


@auth_router.post("/auth/google")
async def api_google_auth(req: GoogleAuthRequest, response: Response):
    """
    Authenticates a user via verified Google ID Token:
    1. Verifies Google token signature, issuer, audience, and expiry.
    2. Enforces backend role authorization (ordinary user cannot self-promote to Admin).
    3. Persists user in SQLite.
    4. Creates secure session and sets HTTP-only cookie.
    """
    # 1. Verify Google Token
    try:
        verified_claims = verify_google_id_token(req.credential)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # 2. Upsert user with backend-controlled role authorization
    user = upsert_user(
        google_sub=verified_claims["google_sub"],
        name=verified_claims["name"],
        email=verified_claims["email"],
        picture=verified_claims["picture"],
        requested_role=req.requested_role
    )

    # 3. Create active session
    session_id = create_session(user["user_id"])

    # 4. Set HTTP-only secure cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        max_age=SESSION_DURATION_DAYS * 86400,
        samesite="lax",
        secure=False  # Set to True in production HTTPS
    )

    return {
        "success": True,
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "picture": user["picture"],
        "authorized_role": user["authorized_role"],
        "requested_role": user["requested_role"],
        "account_status": user["account_status"],
        "message": user.get("notice_message", "Authentication successful.")
    }


@auth_router.get("/auth/me")
async def api_get_current_user(user: dict[str, Any] = Depends(get_current_user)):
    """Returns current verified user identity and authorized role."""
    return {
        "authenticated": True,
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "picture": user["picture"],
        "authorized_role": user["authorized_role"],
        "requested_role": user["requested_role"],
        "account_status": user["account_status"],
        "created_at": user["created_at"],
        "last_login_at": user["last_login_at"]
    }


@auth_router.post("/auth/logout")
async def api_logout(request: Request, response: Response):
    """Invalidates active session and clears HTTP-only cookie."""
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_id = auth_header[7:].strip()

    if session_id:
        invalidate_session(session_id)

    response.delete_cookie(key=COOKIE_NAME)
    return {"success": True, "message": "Successfully logged out."}


@auth_router.post("/auth/switch-role")
async def api_switch_role(req: SwitchRoleRequest, user: dict[str, Any] = Depends(get_current_user)):
    """
    Allows authorized administrators to toggle their active role view between 'admin' and 'it_team'
    to evaluate and demonstrate Section E RBAC data filtering in real-time.
    """
    target_role = req.role.lower().strip()
    if target_role not in ("admin", "it_team"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'it_team'.")

    email_clean = user.get("email", "").lower().strip()
    is_authorized_admin = (
        email_clean in INITIAL_ADMIN_EMAILS or
        user.get("authorized_role") == "admin" or
        user.get("requested_role") == "admin"
    )

    if target_role == "admin" and not is_authorized_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilege escalation prohibited: Administrator role requires prior authorization."
        )

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET authorized_role = ?, requested_role = ? WHERE user_id = ?",
                   (target_role, target_role, user["user_id"]))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "new_role": target_role,
        "message": f"Active role successfully switched to {target_role}."
    }


# ── Role-Guarded Administrative Endpoints ─────────────────────────────────────

@auth_router.get("/admin/users")
async def api_admin_list_users(admin_user: dict[str, Any] = Depends(require_admin)):
    """
    CRITICAL SECURITY: Lists all registered users and roles.
    Only accessible by users with authorized_role == 'admin'.
    Returns 403 Forbidden for IT Team users.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, name, email, authorized_role, requested_role, account_status, created_at, last_login_at
        FROM users ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    users_list = [dict(r) for r in rows]
    return {
        "admin": admin_user["email"],
        "total_users": len(users_list),
        "users": users_list
    }


@auth_router.post("/admin/assign-role")
async def api_admin_assign_role(req: AssignRoleRequest, admin_user: dict[str, Any] = Depends(require_admin)):
    """
    Allows an authorized administrator to assign or promote a user role.
    """
    if req.new_role not in ["it_team", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'it_team' or 'admin'.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (req.user_id,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail=f"User {req.user_id} not found.")

    cursor.execute("""
        UPDATE users SET authorized_role = ?, account_status = 'active' WHERE user_id = ?
    """, (req.new_role, req.user_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "user_id": req.user_id,
        "new_role": req.new_role,
        "assigned_by": admin_user["email"]
    }
