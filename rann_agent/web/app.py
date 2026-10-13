"""
RANN Agent Web Application

Re-exports the FastAPI app for use with uvicorn/test client.
"""

from rann_agent.api.server import app  # noqa: F401

__all__ = ['app']