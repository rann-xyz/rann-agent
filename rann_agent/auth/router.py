"""
Authentication Router for RANN Public API

Provides:
- POST /auth/register - User registration with CSRF token
- POST /auth/login - User login with session creation
- POST /auth/logout - Session revocation with CSRF
- GET /auth/session - Session validation

Session storage: Database-backed with HTTP-only cookies
"""

import secrets
import hashlib
import base64
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field

from rann_agent.storage.database import Database

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["authentication"])

# Configuration
SESSION_TTL_HOURS = 24
CSRF_TOKEN_LENGTH = 32
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_REGISTER = 5
RATE_LIMIT_LOGIN = 10

# Password requirements
MIN_PASSWORD_LENGTH = 8


# ============== REQUEST/RESPONSE MODELS ==============

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SessionResponse(BaseModel):
    authenticated: bool
    user: Optional[dict] = None


class AuthUser:
    """Authenticated user context."""
    def __init__(self, user_id: str, email: str, role: str, csrf_token: str = None):
        self.id = user_id
        self.email = email
        self.role = role
        self.csrf_token = csrf_token
    
    def is_admin(self) -> bool:
        return self.role == "admin"


# ============== HELPER FUNCTIONS ==============

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(32)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000, dklen=64)
    return f"pbkdf2_sha256$600000${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    parts = stored_hash.split('$')
    if len(parts) != 4 or parts[0] != 'pbkdf2_sha256':
        return False
    
    try:
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2])
        stored_dk = base64.b64decode(parts[3])
    except Exception:
        return False
    
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, dklen=64)
    return hmac.compare_digest(dk, stored_dk)


def generate_session_id() -> str:
    """Generate cryptographically random session ID."""
    return f"sess_{secrets.token_urlsafe(32)}"


def hash_session_token(token: str) -> str:
    """Hash session token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_csrf_token() -> str:
    """Generate CSRF token."""
    return secrets.token_urlsafe(32)


def hash_csrf_token(token: str) -> str:
    """Hash CSRF token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_csrf(request: Request, expected_hash: str) -> bool:
    """Verify CSRF token from request header."""
    token = request.headers.get("X-CSRF-Token")
    if not token:
        return False
    return hmac.compare_digest(hash_csrf_token(token), expected_hash)


def get_client_ip(request: Request) -> str:
    """
    Get client IP from request, respecting trusted proxies.
    
    For Vercel/production: only trust X-Forwarded-For from known proxy IPs.
    For local development: use direct connection IP.
    
    Default behavior: do NOT trust forwarded headers unless explicitly configured.
    """
    # Check if proxy headers should be trusted
    trust_proxy = False
    trusted_proxy_ips = []
    
    import os
    if os.environ.get("RANN_TRUST_PROXY", "false").lower() == "true":
        trust_proxy = True
        proxy_ips = os.environ.get("RANN_TRUSTED_PROXY_IPS", "")
        trusted_proxy_ips = [ip.strip() for ip in proxy_ips.split(",") if ip.strip()]
    
    # If trusting proxies, check X-Forwarded-For
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get the first IP (original client)
            client_ip = forwarded.split(",")[0].strip()
            # Verify immediate peer is trusted
            if request.client and request.client.host in trusted_proxy_ips:
                return client_ip
    
    # Default: use direct connection IP
    if request.client:
        return request.client.host
    return "unknown"


# ============== RATE LIMITING ==============

_rate_limits: dict[str, list[float]] = {}

def check_rate_limit(key: str, max_requests: int, window: int) -> bool:
    """Check rate limit for given key."""
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - window
    
    if key not in _rate_limits:
        _rate_limits[key] = []
    
    _rate_limits[key] = [t for t in _rate_limits[key] if t > cutoff]
    
    if len(_rate_limits[key]) >= max_requests:
        return False
    
    _rate_limits[key].append(now)
    return True


# ============== CSRF VALIDATION ==============

def csrf_required(func):
    """Decorator to require CSRF token for authenticated requests."""
    async def wrapper(*args, **kwargs):
        request = kwargs.get('request') or (args[0] if args else None)
        user = kwargs.get('user')
        
        if not user or not request:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get expected CSRF hash from database
        db = Database()
        conn = db._get_conn()
        row = conn.execute(
            "SELECT csrf_token_hash FROM sessions WHERE session_id = (SELECT session_id FROM sessions WHERE user_id = ? LIMIT 1)",
            (user.id,)
        ).fetchone()
        
        if not row or not row['csrf_token_hash']:
            raise HTTPException(status_code=403, detail="CSRF validation failed")
        
        if not verify_csrf(request, row['csrf_token_hash']):
            raise HTTPException(status_code=403, detail="CSRF validation failed")
        
        return await func(*args, **kwargs)
    
    return wrapper


# ============== ENDPOINTS ==============

@router.post("/register")
async def register(request: RegisterRequest, resp: Response):
    """Register a new user."""
    client_ip = get_client_ip(request)
    ip_key = f"register:{client_ip}"
    
    if not check_rate_limit(ip_key, RATE_LIMIT_REGISTER, RATE_LIMIT_WINDOW):
        raise HTTPException(status_code=429, detail="Too many registration attempts")
    
    db = Database()
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if email exists
    try:
        conn = db._get_conn()
        row = conn.execute("SELECT id FROM users WHERE email = ?", (request.email.lower(),)).fetchone()
        if row:
            raise HTTPException(status_code=409, detail="Email already registered")
    except Exception as e:
        logger.error("register_db_error", error=str(e))
        raise HTTPException(status_code=500, detail="Registration failed")
    
    # Create user
    user_id = f"user_{secrets.token_urlsafe(16)}"
    password_hash = hash_password(request.password)
    
    # Generate CSRF token
    csrf_token = generate_csrf_token()
    csrf_hash = hash_csrf_token(csrf_token)
    
    try:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, request.email.lower(), password_hash, "user", now, now)
        )
        conn.execute(
            "INSERT INTO sessions (session_id, user_id, token_hash, csrf_token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (generate_session_id(), user_id, "", csrf_hash, now, (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat())
        )
        conn.commit()
    except Exception as e:
        logger.error("register_db_insert_error", error=str(e))
        raise HTTPException(status_code=500, detail="Registration failed")
    
    # Create session for new user
    session_id = generate_session_id()
    token_hash = hash_session_token(session_id)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, token_hash, csrf_token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, user_id, token_hash, csrf_hash, now, expires_at.isoformat())
    )
    conn.commit()
    
    # Set secure cookie
    cookie_params = {
        "key": "session",
        "value": session_id,
        "httponly": True,
        "secure": False,  # Set True in production with HTTPS
        "samesite": "Lax",
        "path": "/",
        "expires": expires_at,
    }
    resp.set_cookie(**cookie_params)
    
    return {"authenticated": True, "user": {"id": user_id, "email": request.email.lower(), "role": "user"}}


@router.post("/login")
async def login(request: LoginRequest, resp: Response):
    """Authenticate user and create session."""
    client_ip = get_client_ip(request)
    ip_key = f"login:{client_ip}"
    
    if not check_rate_limit(ip_key, RATE_LIMIT_LOGIN, RATE_LIMIT_WINDOW):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    
    db = Database()
    now = datetime.now(timezone.utc).isoformat()
    
    # Find user
    conn = db._get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (request.email.lower(),)).fetchone()
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user = dict(row)
    
    # Verify password
    if not verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if disabled
    if user.get('disabled_at'):
        raise HTTPException(status_code=401, detail="Account disabled")
    
    user_id = user['id']
    
    # Revoke existing sessions (one active session policy)
    try:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    except Exception:
        pass
    
    # Create new session
    session_id = generate_session_id()
    csrf_token = generate_csrf_token()
    token_hash = hash_session_token(session_id)
    csrf_hash = hash_csrf_token(csrf_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    
    try:
        conn.execute(
            "INSERT INTO sessions (session_id, user_id, token_hash, csrf_token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user_id, token_hash, csrf_hash, now, expires_at.isoformat())
        )
        conn.commit()
    except Exception as e:
        logger.error("login_session_error", error=str(e))
        raise HTTPException(status_code=500, detail="Login failed")
    
    # Set secure cookie
    cookie_params = {
        "key": "session",
        "value": session_id,
        "httponly": True,
        "secure": False,  # Set True in production with HTTPS
        "samesite": "Lax",
        "path": "/",
        "expires": expires_at,
    }
    resp.set_cookie(**cookie_params)
    
    logger.info("user_logged_in", user_id=user_id, session_id=session_id)
    
    return {
        "authenticated": True,
        "user": {"id": user_id, "email": user['email'], "role": user['role']}
    }


@router.post("/logout")
async def logout(request: Request, resp: Response):
    """Revoke current session."""
    session_id = request.cookies.get("session")
    
    if session_id:
        db = Database()
        conn = db._get_conn()
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE session_id = ?", 
            (datetime.now(timezone.utc).isoformat(), session_id)
        )
        conn.commit()
        
        # Clear cookie
        resp.delete_cookie("session", path="/")
    
    return {"authenticated": False, "message": "Logged out"}


@router.get("/session")
async def get_session(request: Request):
    """Get current session info."""
    session_id = request.cookies.get("session")
    
    if not session_id:
        return {"authenticated": False}
    
    db = Database()
    conn = db._get_conn()
    
    # Validate session
    row = conn.execute(
        """SELECT s.*, u.id as user_id, u.email, u.role 
           FROM sessions s 
           JOIN users u ON s.user_id = u.id 
           WHERE s.session_id = ?""",
        (session_id,)
    ).fetchone()
    
    if not row:
        return {"authenticated": False}
    
    session = dict(row)
    
    # Check expiration
    expires_at = datetime.fromisoformat(session['expires_at'])
    if datetime.now(timezone.utc) > expires_at:
        return {"authenticated": False}
    
    # Check revocation
    if session.get('revoked_at'):
        return {"authenticated": False}
    
    # Update last seen
    conn.execute(
        "UPDATE sessions SET last_seen_at = ? WHERE session_id = ?",
        (datetime.now(timezone.utc).isoformat(), session_id)
    )
    conn.commit()
    
    return {
        "authenticated": True,
        "user": {
            "id": session['user_id'],
            "email": session['email'],
            "role": session['role']
        }
    }


# ============== DEPENDENCY ==============

async def get_current_user(request: Request) -> Optional[AuthUser]:
    """Dependency to get authenticated user from session."""
    session_id = request.cookies.get("session")
    
    if not session_id:
        return None
    
    db = Database()
    conn = db._get_conn()
    
    row = conn.execute(
        """SELECT s.*, u.id as user_id, u.email, u.role 
           FROM sessions s 
           JOIN users u ON s.user_id = u.id 
           WHERE s.session_id = ?""",
        (session_id,)
    ).fetchone()
    
    if not row:
        return None
    
    session = dict(row)
    expires_at = datetime.fromisoformat(session['expires_at'])
    
    if datetime.now(timezone.utc) > expires_at:
        return None
    
    if session.get('revoked_at'):
        return None
    
    return AuthUser(
        user_id=session['user_id'],
        email=session['email'],
        role=session['role']
    )


def require_auth(user: AuthUser = Depends(get_current_user)):
    """Dependency that requires authentication."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(user: AuthUser = Depends(get_current_user)):
    """Dependency that requires admin role."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not user.is_admin():
        raise HTTPException(status_code=403, detail="Admin access required")
    return user