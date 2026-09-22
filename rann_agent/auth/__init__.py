"""
RANN Authentication and User Identity System
Provides secure authentication with password hashing, server-side sessions, and user isolation.

PASSWORD HASHING: PBKDF2-HMAC-SHA256 with 600,000 iterations
SESSION STORAGE: Database-backed with HTTP-only cookies
"""

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple, Callable

import structlog

logger = structlog.get_logger()


class User:
    """User model with secure password storage."""
    
    def __init__(
        self,
        user_id: str,
        email: str,
        password_hash: str,
        role: str = "user",
        created_at: Optional[datetime] = None,
        disabled_at: Optional[datetime] = None,
    ):
        self.id = user_id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.created_at = created_at or datetime.now(timezone.utc)
        self.disabled_at = disabled_at
    
    def is_disabled(self) -> bool:
        return self.disabled_at is not None
    
    def is_admin(self) -> bool:
        return self.role == "admin"


class Session:
    """Server-side session with security controls."""
    
    def __init__(
        self,
        session_id: str,
        user_id: str,
        created_at: datetime,
        expires_at: datetime,
        revoked_at: Optional[datetime] = None,
        token_hash: Optional[str] = None,
    ):
        self.id = session_id
        self.user_id = user_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.revoked_at = revoked_at
        self.token_hash = token_hash
    
    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.revoked_at:
            return False
        if now > self.expires_at:
            return False
        return True
    
    def revoke(self):
        self.revoked_at = datetime.now(timezone.utc)


class PasswordHasher:
    """Secure password hashing using PBKDF2-HMAC-SHA256."""
    
    # Production-ready settings
    ALGORITHM = "pbkdf2_sha256"
    ITERATIONS = 600000
    SALT_LENGTH = 32
    HASH_LENGTH = 64
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password securely using PBKDF2-HMAC-SHA256."""
        import base64
        salt = secrets.token_bytes(cls.SALT_LENGTH)
        
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            cls.ITERATIONS,
            dklen=cls.HASH_LENGTH
        )
        
        return f"{cls.ALGORITHM}${cls.ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    
    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        """Verify a password against stored hash."""
        import base64
        
        parts = stored_hash.split('$')
        if len(parts) != 4:
            return False
        
        algorithm, iterations, salt_b64, hash_b64 = parts
        
        if algorithm != cls.ALGORITHM:
            return False
        
        try:
            salt = base64.b64decode(salt_b64)
            stored_dk = base64.b64decode(hash_b64)
        except Exception:
            return False
        
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            int(iterations),
            dklen=cls.HASH_LENGTH
        )
        
        return hmac.compare_digest(dk, stored_dk)


class IpBinding:
    """IP binding for abuse control using HMAC-SHA256."""
    
    def __init__(
        self,
        ip_hash: str,
        user_id: str,
        created_at: datetime,
        expires_at: datetime,
        last_seen_at: datetime,
    ):
        self.ip_hash = ip_hash
        self.user_id = user_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.last_seen_at = last_seen_at
    
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class HashHelper:
    """Helper for secure hashing with server-side secret."""
    
    _secret: Optional[bytes] = None
    
    @classmethod
    def get_secret(cls) -> bytes:
        """Get or generate the HMAC secret."""
        if cls._secret is None:
            # In production, use environment variable
            import os
            secret_env = os.environ.get("RANN_IP_BINDING_SECRET", "")
            if secret_env:
                cls._secret = secret_env.encode()
            else:
                # Generate for development
                cls._secret = secrets.token_bytes(32)
        return cls._secret
    
    @classmethod
    def hash_ip(cls, ip: str) -> str:
        """Hash IP using HMAC-SHA256 with server secret."""
        normalized = ip.strip("[]").lower()
        return hmac.new(cls.get_secret(), normalized.encode(), hashlib.sha256).hexdigest()


class RateLimiter:
    """In-memory rate limiter for API protection."""
    
    def __init__(self):
        self._counters: dict[str, list[float]] = {}
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if request is allowed under rate limit."""
        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - window_seconds
        
        if key not in self._counters:
            self._counters[key] = []
        
        # Remove old entries
        self._counters[key] = [t for t in self._counters[key] if t > cutoff]
        
        if len(self._counters[key]) >= max_requests:
            return False
        
        self._counters[key].append(now)
        return True


# Global instances
rate_limiter = RateLimiter()


# ============== AUTHENTICATION FUNCTIONS ==============

def generate_session_id() -> str:
    """Generate cryptographically random session ID."""
    return f"sess_{secrets.token_urlsafe(32)}"


def generate_user_id() -> str:
    """Generate cryptographically random user ID."""
    return f"user_{secrets.token_urlsafe(16)}"


def hash_session_token(token: str) -> str:
    """Hash session token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Validate password meets minimum requirements."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    return True, ""


# Export commonly used items
__all__ = [
    'User',
    'Session', 
    'PasswordHasher',
    'IpBinding',
    'HashHelper',
    'RateLimiter',
    'generate_session_id',
    'generate_user_id',
    'hash_session_token',
    'validate_password_strength',
    'rate_limiter',
]