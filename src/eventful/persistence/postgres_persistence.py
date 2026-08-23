"""Optional PostgreSQL event-store boundary.

The shell validates the ``postgres`` extra and retains a DSN. Schema management,
append/read operations, ordering, and transaction semantics remain deferred.
"""
from __future__ import annotations
from eventful._optional import require_optional

class PostgresPersistence:
    """Experimental shell for PostgreSQL-backed event persistence."""
    def __init__(self, dsn: str) -> None:
        """Validate the optional dependency and retain the future database DSN."""
        self.asyncpg = require_optional("PostgresPersistence", "postgres", "asyncpg")
        self.dsn = dsn
