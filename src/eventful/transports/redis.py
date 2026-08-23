"""Optional Redis transport boundary.

The current class validates the ``redis`` extra and stores connection settings;
publishing, consuming, reconnect, and ownership semantics remain deferred.
"""
from __future__ import annotations
from eventful._optional import require_optional

class RedisTransport:
    """Experimental shell for a future Redis broker transport."""
    def __init__(self, url: str) -> None:
        """Validate the optional dependency and retain the future connection URL."""
        self.redis = require_optional("RedisTransport", "redis", "redis")
        self.url = url
