"""Shared rate limiter instance for all routers (NFR-012).

Creates a single Limiter that main.py attaches to app.state and routers
use for @limiter.limit() decorators. This avoids fragmented rate limit
counters across multiple Limiter instances.
"""

from app.config import RATE_LIMIT_ENABLED

limiter = None

if RATE_LIMIT_ENABLED:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
