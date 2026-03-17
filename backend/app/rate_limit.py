"""Shared rate limiter for the CollabMark API.

API-key-authenticated requests get a separate, more generous bucket
(keyed on the first 16 chars of the key) so automated agents aren't
throttled as aggressively as anonymous/cookie-based users who are
keyed by IP address.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_limit_key(request: Request) -> str:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:16]}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["200/minute"],
)
