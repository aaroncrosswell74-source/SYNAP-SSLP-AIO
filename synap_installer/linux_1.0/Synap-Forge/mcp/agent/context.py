"""
Request context helpers for tracking request IDs and headers across async/thread boundaries.
"""

import uuid
import contextvars
from typing import Dict, Any


_request_id = contextvars.ContextVar(
    "request_id",
    default=None
)

_request_headers = contextvars.ContextVar(
    "request_headers",
    default={}
)


def set_request_id(request_id: str = None) -> str:
    """Set the current request ID. Generates one if not provided."""
    if request_id is None:
        request_id = str(uuid.uuid4())

    _request_id.set(request_id)
    return request_id


def get_request_id() -> str:
    """Get the current request ID. Generates one if not set."""
    request_id = _request_id.get()

    if request_id is None:
        request_id = set_request_id()

    return request_id


def generate_request_id() -> str:
    """Generate a short unique request ID."""
    return uuid.uuid4().hex[:8]


def set_request_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    """Set the current request headers."""
    _request_headers.set(headers)
    return headers


def get_request_headers() -> Dict[str, Any]:
    """Get the current request headers."""
    return _request_headers.get()
