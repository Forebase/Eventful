"""Redis transport placeholder with precise optional dependency errors."""
from __future__ import annotations
from eventful._optional import require_optional

class RedisTransport:
    """Experimental shell for a future Redis broker transport."""
    def __init__(self, url: str) -> None:
        self.redis = require_optional("RedisTransport", "redis", "redis")
        self.url = url
