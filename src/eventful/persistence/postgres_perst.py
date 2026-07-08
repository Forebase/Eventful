"""
PostgreSQL-based event persistence.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Optional

try:
    import asyncpg
    from asyncpg.pool import Pool
except ImportError:
    asyncpg = None

from src.eventful.event import Event


class PostgresPersistence:
    """
    PostgreSQL-based event persistence.
    """

    def __init__(self, dsn: str, table_name: str = "events"):
        """
        Initialize PostgreSQL persistence.

        Parameters
        ----------
        dsn : str
            PostgreSQL connection string.
        table_name : str, optional
            Name of the events table.
        """
        if asyncpg is None:
            raise ImportError(
                "PostgreSQL persistence requires 'asyncpg'. "
                "Install with 'pip install eventful[postgres]'"
            )

        self.dsn = dsn
        self.table_name = table_name
        self._pool: Optional[Pool] = None

    async def connect(self) -> None:
        """Create connection pool and ensure table exists."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.dsn,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            await self._create_table()

    async def _create_table(self) -> None:
        """Create events table if it doesn't exist."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id SERIAL PRIMARY KEY,
                    type TEXT NOT NULL,
                    payload BYTEA,
                    metadata JSONB,
                    tags TEXT[],
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Create index for efficient type-based queries
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_type 
                ON {self.table_name} (type)
            """)

            # Create index for efficient tag-based queries
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tags 
                ON {self.table_name} USING GIN (tags)
            """)

    async def append(self, event: Event) -> int:
        """
        Append an event to the database.

        Parameters
        ----------
        event : Event
            Event to store.

        Returns
        -------
        int
            ID of the inserted event.
        """
        await self.connect()

        # Serialize payload based on type
        serialized_payload = None
        if event.payload is not None:
            if isinstance(event.payload, (str, bytes)):
                serialized_payload = str(event.payload).encode()
            else:
                try:
                    import json
                    serialized_payload = json.dumps(event.payload).encode()
                except (TypeError, ValueError):
                    serialized_payload = str(event.payload).encode()

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(f"""
                INSERT INTO {self.table_name} (type, payload, metadata, tags)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, event.type, serialized_payload, event.metadata, list(event.tags))

            return result['id']

    async def replay(self, start_id: int = 0, batch: int = 1000) -> AsyncIterator[Event]:
        """
        Replay events from the database.

        Parameters
        ----------
        start_id : int, optional
            Starting event ID.
        batch : int, optional
            Batch size for each query.

        Yields
        ------
        Event
            Events in insertion order.
        """
        await self.connect()

        current_id = start_id

        while True:
            async with self._pool.acquire() as conn:
                records = await conn.fetch(f"""
                    SELECT id, type, payload, metadata, tags
                    FROM {self.table_name}
                    WHERE id >= $1
                    ORDER BY id
                    LIMIT $2
                """, current_id, batch)

                if not records:
                    break

                for record in records:
                    # Deserialize payload
                    payload = None
                    if record['payload']:
                        try:
                            import json
                            payload = json.loads(record['payload'].decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            payload = record['payload'].decode()

                    event = Event(
                        type=record['type'],
                        payload=payload,
                        metadata=record['metadata'],
                        tags=set(record['tags'])
                    )
                    yield event

                    current_id = record['id'] + 1

    async def get_event_count(self) -> int:
        """Get total number of events in the database."""
        await self.connect()

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(f"""
                SELECT COUNT(*) as count FROM {self.table_name}
            """)
            return result['count']

    async def get_events_by_type(self, event_type: str, limit: int = 100) -> list[Event]:
        """Get events filtered by type."""
        await self.connect()

        events = []
        async with self._pool.acquire() as conn:
            records = await conn.fetch(f"""
                SELECT id, type, payload, metadata, tags
                FROM {self.table_name}
                WHERE type = $1
                ORDER BY id
                LIMIT $2
            """, event_type, limit)

            for record in records:
                payload = None
                if record['payload']:
                    try:
                        import json
                        payload = json.loads(record['payload'].decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        payload = record['payload'].decode()

                events.append(Event(
                    type=record['type'],
                    payload=payload,
                    metadata=record['metadata'],
                    tags=set(record['tags'])
                ))

        return events

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
