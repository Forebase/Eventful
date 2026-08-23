"""Durable PostgreSQL implementation of Eventful's event-store contract.

The store persists codec bytes in an append-only table ordered by a database
identity position. It owns pools it creates, supports explicit schema migration,
idempotent appends, optimistic expected-position checks, and repeatable read
snapshots. It does not delete, update, project, or publish stored events.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any

from eventful._optional import require_optional
from eventful.codecs import JsonCodec
from eventful.contracts import Codec
from eventful.event import Event
from eventful.exceptions import OptimisticConcurrencyError, StoreError

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCHEMA_VERSION = 1


class PostgresPersistence:
    """Append and replay durable event snapshots from one PostgreSQL table."""

    def __init__(
        self,
        dsn: str,
        *,
        table: str = "eventful_events",
        codec: Codec | None = None,
        pool: Any | None = None,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
        command_timeout: float = 60.0,
        read_batch_size: int = 500,
    ) -> None:
        """Configure a lazy store and optionally accept a caller-owned pool."""
        if not dsn:
            raise ValueError("dsn must not be empty")
        if not _IDENTIFIER.fullmatch(table) or len(table) > 40:
            raise ValueError(
                "table must be a simple PostgreSQL identifier of at most 40 characters"
            )
        if min_pool_size < 0 or max_pool_size < 1 or min_pool_size > max_pool_size:
            raise ValueError("invalid PostgreSQL pool size range")
        if command_timeout <= 0:
            raise ValueError("command_timeout must be greater than zero")
        if read_batch_size < 1:
            raise ValueError("read_batch_size must be greater than zero")

        self.asyncpg = require_optional("PostgresPersistence", "postgres", "asyncpg")
        self.dsn = dsn
        self.table = table
        self.codec = codec or JsonCodec()
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.command_timeout = command_timeout
        self.read_batch_size = read_batch_size
        self._pool = pool
        self._owns_pool = pool is None
        self._closed = False
        self._open_lock = asyncio.Lock()
        self._quoted_table = self._quote_identifier(table)
        self._schema_table = self._quote_identifier(f"{table}_schema")

    async def open(self) -> None:
        """Create the owned connection pool idempotently without migrating."""
        async with self._open_lock:
            self._ensure_not_closed()
            if self._pool is not None:
                return
            try:
                self._pool = await self.asyncpg.create_pool(
                    self.dsn,
                    min_size=self.min_pool_size,
                    max_size=self.max_pool_size,
                    command_timeout=self.command_timeout,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise StoreError("PostgreSQL pool creation failed") from exc

    async def migrate(self) -> None:
        """Apply forward-only, concurrency-safe schema migrations to version 1."""
        pool = await self._require_pool()
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        "SELECT pg_advisory_xact_lock(hashtext($1))", self.table
                    )
                    await connection.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self._schema_table} (
                            singleton BOOLEAN PRIMARY KEY DEFAULT TRUE
                                CHECK (singleton),
                            version INTEGER NOT NULL
                        )
                        """
                    )
                    await connection.execute(
                        f"""
                        INSERT INTO {self._schema_table} (singleton, version)
                        VALUES (TRUE, 0)
                        ON CONFLICT (singleton) DO NOTHING
                        """
                    )
                    version = await connection.fetchval(
                        f"SELECT version FROM {self._schema_table} "
                        "WHERE singleton = TRUE FOR UPDATE"
                    )
                    if version > _SCHEMA_VERSION:
                        raise StoreError(
                            f"PostgreSQL schema version {version} is newer than "
                            f"supported version {_SCHEMA_VERSION}"
                        )
                    if version < 1:
                        await connection.execute(
                            f"""
                            CREATE TABLE {self._quoted_table} (
                                position BIGINT GENERATED BY DEFAULT AS IDENTITY
                                    PRIMARY KEY,
                                event_type TEXT NOT NULL,
                                media_type TEXT NOT NULL,
                                encoded_event BYTEA NOT NULL,
                                idempotency_key TEXT UNIQUE,
                                recorded_at TIMESTAMPTZ NOT NULL
                                    DEFAULT clock_timestamp()
                            )
                            """
                        )
                        await connection.execute(
                            f"CREATE INDEX {self._quote_identifier(f'{self.table}_type_position_idx')} "
                            f"ON {self._quoted_table} (event_type, position)"
                        )
                        await connection.execute(
                            f"UPDATE {self._schema_table} SET version = 1 "
                            "WHERE singleton = TRUE"
                        )
        except (StoreError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise StoreError("PostgreSQL migration failed") from exc

    async def append(
        self,
        event: Event,
        *,
        idempotency_key: str | None = None,
        expected_position: str | None = None,
    ) -> str:
        """Atomically append an encoded event and return its ordered position.

        Reusing an idempotency key with identical bytes returns the original
        position. Reusing it for a different event fails. When supplied,
        ``expected_position`` must equal the current maximum position; ``"-1"``
        represents an empty stream.
        """
        if not isinstance(event, Event):
            raise TypeError("event must be an Event")
        if not event.type:
            raise StoreError("event type must not be empty")
        if idempotency_key == "":
            raise ValueError("idempotency_key must not be empty")
        expected = self._parse_expected_position(expected_position)
        encoded = self.codec.encode(event)
        pool = await self._require_pool()
        try:
            async with pool.acquire() as connection:
                async with connection.transaction():
                    if expected is not None:
                        await connection.execute(
                            f"LOCK TABLE {self._quoted_table} IN EXCLUSIVE MODE"
                        )
                        current = await connection.fetchval(
                            f"SELECT COALESCE(MAX(position), -1) "
                            f"FROM {self._quoted_table}"
                        )
                        if current != expected:
                            raise OptimisticConcurrencyError(
                                f"expected PostgreSQL position {expected}, "
                                f"found {current}"
                            )
                    row = await connection.fetchrow(
                        f"""
                        INSERT INTO {self._quoted_table} (
                            event_type, media_type, encoded_event, idempotency_key
                        ) VALUES ($1, $2, $3, $4)
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING position
                        """,
                        event.type,
                        self.codec.media_type,
                        encoded,
                        idempotency_key,
                    )
                    if row is not None:
                        return str(row["position"])
                    existing = await connection.fetchrow(
                        f"""
                        SELECT position, event_type, media_type, encoded_event
                        FROM {self._quoted_table}
                        WHERE idempotency_key = $1
                        """,
                        idempotency_key,
                    )
                    if existing is None:
                        raise StoreError("idempotent PostgreSQL append lost its row")
                    if (
                        existing["event_type"] != event.type
                        or existing["media_type"] != self.codec.media_type
                        or bytes(existing["encoded_event"]) != encoded
                    ):
                        raise StoreError(
                            "idempotency key already belongs to a different event"
                        )
                    return str(existing["position"])
        except (StoreError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise StoreError("PostgreSQL append failed") from exc

    async def read(self, *, after: str | None = None) -> AsyncIterator[Event]:
        """Stream a stable ordered snapshot strictly after an opaque position.

        A repeatable-read transaction and pool connection remain open until the
        iterator ends or is closed. Rows are fetched in bounded batches.
        """
        position = self._parse_read_position(after)
        pool = await self._require_pool()
        try:
            async with pool.acquire() as connection:
                async with connection.transaction(
                    isolation="repeatable_read", readonly=True
                ):
                    rows = connection.cursor(
                        f"""
                        SELECT position, event_type, media_type, encoded_event
                        FROM {self._quoted_table}
                        WHERE position > $1
                        ORDER BY position ASC
                        """,
                        position,
                        prefetch=self.read_batch_size,
                    )
                    async for row in rows:
                        if row["media_type"] != self.codec.media_type:
                            raise StoreError(
                                f"unsupported stored media type: {row['media_type']!r}"
                            )
                        event = self.codec.decode(bytes(row["encoded_event"]))
                        if event.type != row["event_type"]:
                            raise StoreError(
                                "stored event type does not match encoded event"
                            )
                        yield event
        except StoreError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise StoreError("PostgreSQL read failed") from exc

    async def close(self) -> None:
        """Close an owned pool idempotently and reject later operations."""
        async with self._open_lock:
            if self._closed:
                return
            self._closed = True
            pool, self._pool = self._pool, None
        if pool is not None and self._owns_pool:
            try:
                await pool.close()
            except Exception as exc:
                raise StoreError("PostgreSQL pool close failed") from exc

    async def __aenter__(self) -> PostgresPersistence:
        """Open the pool without applying schema migrations implicitly."""
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Close owned resources when leaving an asynchronous context."""
        await self.close()

    async def _require_pool(self) -> Any:
        """Return an open pool, creating an owned pool lazily when necessary."""
        self._ensure_not_closed()
        await self.open()
        if self._pool is None:
            raise StoreError("PostgreSQL pool is unavailable")
        return self._pool

    def _ensure_not_closed(self) -> None:
        """Reject operations after lifecycle shutdown."""
        if self._closed:
            raise StoreError("PostgreSQL event store is closed")

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Quote an already validated PostgreSQL identifier."""
        return f'"{identifier}"'

    @staticmethod
    def _parse_read_position(position: str | None) -> int:
        """Translate an opaque position to the exclusive SQL lower bound."""
        if position is None:
            return -1
        try:
            parsed = int(position)
        except (TypeError, ValueError) as exc:
            raise StoreError(f"invalid PostgreSQL position: {position!r}") from exc
        if parsed < 0 or str(parsed) != position:
            raise StoreError(f"invalid PostgreSQL position: {position!r}")
        return parsed

    @staticmethod
    def _parse_expected_position(position: str | None) -> int | None:
        """Parse an optional expected position, accepting -1 for an empty store."""
        if position is None:
            return None
        if position == "-1":
            return -1
        return PostgresPersistence._parse_read_position(position)


__all__ = ["PostgresPersistence"]
