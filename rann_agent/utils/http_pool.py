"""
HTTP Connection Pool for RANN Agent.

Provides a shared httpx client with connection pooling.
Configured for high-throughput API calls.
"""
import httpx
import threading
from typing import Optional
import structlog

logger = structlog.get_logger()

# Pool configuration
POOL_LIMITS = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=100,
    keepalive_expiry=120.0,
)

TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=60.0,
    write=30.0,
    pool=15.0,
)

# Shared client (lazy-initialized)
_client: Optional[httpx.AsyncClient] = None
_client_lock = threading.Lock()


def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared HTTP client with connection pooling."""
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.AsyncClient(
                limits=POOL_LIMITS,
                timeout=TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": "RANN-Agent/1.0",
                    "Accept": "application/json",
                },
            )
            logger.info("http_pool_initialized", limits=POOL_LIMITS)
        return _client


async def close_http_client():
    """Close the shared HTTP client."""
    global _client
    with _client_lock:
        if _client is not None:
            await _client.aclose()
            _client = None
            logger.info("http_pool_closed")


class HTTPPoolMixin:
    """
    Mixin for classes that need HTTP calls.
    Provides self.http (shared pooled client) and self._request().
    """

    def __init__(self):
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = get_http_client()
        return self._http

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request using the pooled client."""
        return await self.http.request(method, url, **kwargs)