"""PostgreSQL persistence placeholder with precise optional dependency errors."""
from __future__ import annotations
from eventful._optional import require_optional

class PostgresPersistence:
    """Experimental shell for PostgreSQL-backed event persistence."""
    def __init__(self, dsn: str) -> None:
        self.asyncpg = require_optional("PostgresPersistence", "postgres", "asyncpg")
        self.dsn = dsn
