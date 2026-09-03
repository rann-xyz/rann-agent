"""
API Client for RANN Agent
Async HTTP client for programmatic access: execute, stream, status, cancel.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional, AsyncIterator, Dict, Any
from urllib.parse import urljoin

import httpx
import structlog

from rann_agent.core.exceptions import RannAgentError


logger = structlog.get_logger()


class RunStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

    @property
    def is_terminal(self) -> bool:
        return self in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


@dataclass
class RunResult:
    run_id: str
    status: RunStatus
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def is_terminal(self) -> bool:
        return self.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


@dataclass
class StreamEvent:
    event_type: str
    data: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None


class APIClientError(RannAgentError):
    pass


class AuthenticationError(APIClientError):
    pass


class APIClient:
    """
    Async HTTP client for RANN Agent API.
    
    Methods:
        execute(task) -> RunResult
        stream(task) -> AsyncIterator[StreamEvent]
        get_status(run_id) -> RunResult
        cancel(run_id) -> RunResult
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._headers: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("api_client_init", base_url=self.base_url, timeout=self.timeout)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        client = await self._get_client()
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        delay = 1.0

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code == 401:
                    raise AuthenticationError("Authentication failed")
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= 1.5
                    continue
                raise APIClientError("Request timed out")
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= 1.5
                    continue
                raise APIClientError(f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= 1.5
                    continue
                raise APIClientError(f"Request failed: {e}")
        raise APIClientError("Max retries exceeded")

    async def execute(
        self,
        task: str,
        context: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        wait: bool = True,
        poll_interval: float = 0.5,
    ) -> RunResult:
        """Execute a task. Optionally wait for completion."""
        logger.info("api_execute", task=task[:100])
        payload: Dict[str, Any] = {"goal": task}
        if context:
            payload["context"] = context
        if provider:
            payload["provider"] = provider
        if model:
            payload["model"] = model

        try:
            response = await self._request("POST", "/api/execute", json=payload)
            run_id = response.get("session_id", "unknown")
            status = RunStatus(response.get("status", "unknown").upper())

            if wait and not status.is_terminal:
                while True:
                    await asyncio.sleep(poll_interval)
                    result = await self.get_status(run_id)
                    if result.is_terminal:
                        return result

            return RunResult(
                run_id=run_id,
                status=status,
                success=response.get("success", False),
                output=response.get("output"),
                error=response.get("error"),
                metadata=response.get("metadata", {}),
            )
        except Exception as e:
            logger.error("api_execute_failed", error=str(e))
            return RunResult(run_id="error", status=RunStatus.FAILED, success=False, error=str(e))

    async def stream(self, task: str, context: Optional[str] = None) -> AsyncIterator[StreamEvent]:
        """Execute with streaming. Yields StreamEvent objects."""
        logger.info("api_stream", task=task[:100])
        # Fallback: polling-based streaming simulation
        result = await self.execute(task, context, wait=False)
        yield StreamEvent(event_type="session_started", session_id=result.run_id)

        while True:
            await asyncio.sleep(0.1)
            status = await self.get_status(result.run_id)
            if status.status == RunStatus.COMPLETED:
                yield StreamEvent(event_type="complete", session_id=result.run_id)
                break
            elif status.status == RunStatus.FAILED:
                yield StreamEvent(event_type="error", error=status.error)
                break

    async def get_status(self, run_id: str) -> RunResult:
        """Get status of a run."""
        logger.debug("api_get_status", run_id=run_id)
        try:
            response = await self._request("GET", f"/api/status/{run_id}")
            return RunResult(
                run_id=run_id,
                status=RunStatus(response.get("status", "unknown").upper()),
                success=response.get("success", False),
                output=response.get("output"),
                error=response.get("error"),
                metadata=response.get("metadata", {}),
            )
        except Exception as e:
            logger.error("api_get_status_failed", run_id=run_id, error=str(e))
            return RunResult(run_id=run_id, status=RunStatus.UNKNOWN, success=False, error=str(e))

    async def cancel(self, run_id: str) -> RunResult:
        """Cancel a running task."""
        logger.info("api_cancel", run_id=run_id)
        try:
            response = await self._request("POST", f"/api/cancel/{run_id}")
            return RunResult(run_id=run_id, status=RunStatus.CANCELLED, success=True, metadata=response)
        except Exception as e:
            logger.error("api_cancel_failed", run_id=run_id, error=str(e))
            return RunResult(run_id=run_id, status=RunStatus.UNKNOWN, success=False, error=str(e))

    async def __aenter__(self) -> "APIClient":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


async def main() -> None:
    """Example usage."""
    async with APIClient(base_url="http://localhost:8000") as client:
        result = await client.execute("What is 2+2?")
        print(f"Result: {result.output}")


if __name__ == "__main__":
    asyncio.run(main())