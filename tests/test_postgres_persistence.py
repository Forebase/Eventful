"""Validation and service-backed tests for durable PostgreSQL persistence."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

from eventful import Event
from eventful.contracts import EventStore
from eventful.exceptions import OptimisticConcurrencyError, StoreError
from eventful.persistence import PostgresPersistence


def postgres_url() -> str:
    """Return the configured integration DSN or skip service-backed tests."""
    url = os.getenv("EVENTFUL_POSTGRES_URL")
    if url is None:
        pytest.skip("EVENTFUL_POSTGRES_URL is not configured")
    return url


async def collect(
    store: PostgresPersistence, *, after: str | None = None
) -> list[Event]:
    """Materialize an ordered store snapshot for assertions."""
    return [event async for event in store.read(after=after)]


@pytest.fixture
async def postgres_store() -> AsyncIterator[PostgresPersistence]:
    """Create a uniquely named migrated store and remove its schema afterward."""
    table = f"evt_t_{uuid4().hex[:24]}"
    store = PostgresPersistence(postgres_url(), table=table, min_pool_size=1)
    await store.open()
    await store.migrate()
    try:
        yield store
    finally:
        pool = store._pool
        if pool is not None:
            async with pool.acquire() as connection:
                await connection.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                await connection.execute(
                    f'DROP TABLE IF EXISTS "{table}_schema" CASCADE'
                )
        else:
            connection = await store.asyncpg.connect(store.dsn)
            try:
                await connection.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                await connection.execute(
                    f'DROP TABLE IF EXISTS "{table}_schema" CASCADE'
                )
            finally:
                await connection.close()
        await store.close()


def test_postgres_store_validates_configuration() -> None:
    """Reject unsafe identifiers and invalid pool settings before connecting."""
    with pytest.raises(ValueError, match="identifier"):
        PostgresPersistence("postgresql://unused", table="events; DROP TABLE users")
    with pytest.raises(ValueError, match="identifier"):
        PostgresPersistence("postgresql://unused", table="e" * 41)
    with pytest.raises(ValueError, match="pool"):
        PostgresPersistence("postgresql://unused", min_pool_size=4, max_pool_size=2)
    with pytest.raises(ValueError, match="read_batch_size"):
        PostgresPersistence("postgresql://unused", read_batch_size=0)


def test_postgres_store_satisfies_runtime_contract() -> None:
    """Expose the asynchronous event-store capability before connecting."""
    assert isinstance(
        PostgresPersistence("postgresql://localhost/eventful"), EventStore
    )


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_append_read_cursor_and_expected_position(
    postgres_store: PostgresPersistence,
) -> None:
    """Validate ordering, exclusive cursors, and optimistic concurrency."""
    first = Event("account.opened", {"id": 1})
    second = Event("account.credited", {"amount": 5})

    first_position = await postgres_store.append(first, expected_position="-1")
    with pytest.raises(OptimisticConcurrencyError, match="expected"):
        await postgres_store.append(Event("stale"), expected_position="-1")
    second_position = await postgres_store.append(
        second, expected_position=first_position
    )

    assert int(second_position) > int(first_position)
    assert await collect(postgres_store) == [first, second]
    assert await collect(postgres_store, after=first_position) == [second]
    assert await collect(postgres_store, after=second_position) == []


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_idempotency_returns_original_and_rejects_key_reuse(
    postgres_store: PostgresPersistence,
) -> None:
    """Make retried writes safe without accepting conflicting payloads."""
    event = Event("invoice.issued", {"id": "invoice-1"})

    original = await postgres_store.append(event, idempotency_key="request-1")
    repeated = await postgres_store.append(event, idempotency_key="request-1")

    assert repeated == original
    assert await collect(postgres_store) == [event]
    with pytest.raises(StoreError, match="different event"):
        await postgres_store.append(
            Event("invoice.issued", {"id": "invoice-2"}),
            idempotency_key="request-1",
        )


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_read_uses_a_stable_snapshot(
    postgres_store: PostgresPersistence,
) -> None:
    """Exclude appends made after a read snapshot has been fetched."""
    first = Event("first")
    await postgres_store.append(first)
    iterator = postgres_store.read()

    assert await anext(iterator) == first
    await postgres_store.append(Event("second"))

    with pytest.raises(StopAsyncIteration):
        await anext(iterator)
    assert [event.type for event in await collect(postgres_store)] == [
        "first",
        "second",
    ]


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_concurrent_appends_have_unique_ordered_positions(
    postgres_store: PostgresPersistence,
) -> None:
    """Delegate concurrent global ordering to PostgreSQL identity positions."""
    events = [Event("concurrent", {"index": index}) for index in range(20)]

    positions = await asyncio.gather(
        *(postgres_store.append(event) for event in events)
    )
    stored = await collect(postgres_store)

    assert len(set(positions)) == len(events)
    assert len(stored) == len(events)
    assert {event.payload["index"] for event in stored} == set(range(20))


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_reads_stream_across_bounded_batches(
    postgres_store: PostgresPersistence,
) -> None:
    """Exercise asyncpg cursor prefetch without changing ordered semantics."""
    postgres_store.read_batch_size = 2
    events = [Event("batch", {"index": index}) for index in range(5)]
    for event in events:
        await postgres_store.append(event)

    assert await collect(postgres_store) == events


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_invalid_positions_and_closed_lifecycle(
    postgres_store: PostgresPersistence,
) -> None:
    """Translate invalid cursors and reject operations after shutdown."""
    for invalid in ("", "-1", "01", "position"):
        with pytest.raises(StoreError, match="position"):
            await collect(postgres_store, after=invalid)

    await postgres_store.close()
    await postgres_store.close()
    with pytest.raises(StoreError, match="closed"):
        await postgres_store.append(Event("later"))


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_migration_is_idempotent_and_data_survives_reopen() -> None:
    """Reopen an owned pool and retain committed event bytes."""
    table = f"evt_r_{uuid4().hex[:24]}"
    first = PostgresPersistence(postgres_url(), table=table)
    second: PostgresPersistence | None = None
    await first.open()
    try:
        await first.migrate()
        await first.migrate()
        position = await first.append(Event("durable", {"saved": True}))
        await first.close()

        second = PostgresPersistence(postgres_url(), table=table)
        await second.open()
        await second.migrate()

        assert position == "1"
        assert await collect(second) == [Event("durable", {"saved": True})]
    finally:
        cleanup = second or first
        pool = cleanup._pool
        if pool is not None:
            async with pool.acquire() as connection:
                await connection.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                await connection.execute(
                    f'DROP TABLE IF EXISTS "{table}_schema" CASCADE'
                )
        await cleanup.close()
