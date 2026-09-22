"""
Session utilities for getting server-derived user identity.

SECURITY: All user identity comes from authenticated sessions, not client input.
"""

from typing import Optional

# Simulated session store (in production, this would be database-backed)
_session_store = {}

async def get_current_user_id(session_id: Optional[str]) -> Optional[str]:
    """Get user_id from authenticated session.

    Args:
        session_id: Server-derived session identifier

    Returns:
        user_id from session, or None if not authenticated

    SECURITY: session_id must come from server authentication, never from client.
    """
    if not session_id:
        return None

    # In production, verify session in database
    session = _session_store.get(session_id)
    if session:
        return session.get("user_id")

    return None

def register_session(session_id: str, user_id: str):
    """Register a session (called during authentication)."""
    _session_store[session_id] = {"user_id": user_id}

def clear_session(session_id: str):
    """Clear a session (called during logout)."""
    _session_store.pop(session_id, None)