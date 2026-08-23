"""Behavioral conformance tests for provisional architectural contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from eventful import Event, EventBus
from eventful.codecs import JsonCodec
from eventful.contracts import (
    AsyncCloseable,
    Codec,
    DispatcherContract,
    EventBusContract,
    EventStore,
    RouterContract,
)
from eventful.exceptions import CodecError, StoreError
from eventful.stores import InMemoryEventStore


def exercise_codec(codec: Codec) -> None:
    """Apply reusable lossless public-field codec requirements."""
    event = Event(
        type="user.created",
        payload={"name": "Zoë"},
        metadata={"trace": "abc"},
        tags={"audit", "user"},
    )

    decoded = codec.decode(codec.encode(event))

    assert decoded == event
    assert decoded is not event


async def collect(store: EventStore, *, after: str | None = None) -> list[Event]:
    """Materialize an event-store read for reusable assertions."""
    return [event async for event in store.read(after=after)]


async def exercise_event_store(store: EventStore) -> None:
    """Apply reusable position, snapshot, isolation, and lifecycle requirements."""
    first = Event("first", payload={"value": 1})
    second = Event("second", tags={"stored"})

    first_position = await store.append(first)
    second_position = await store.append(second)
    first.payload["value"] = 999

    all_events = await collect(store)
    after_first = await collect(store, after=first_position)

    assert first_position != second_position
    assert [event.type for event in all_events] == ["first", "second"]
    assert all_events[0].payload == {"value": 1}
    assert after_first == [second]

    all_events[0].payload["value"] = -1
    assert (await collect(store))[0].payload == {"value": 1}

    await store.close()
    await store.close()
    with pytest.raises(StoreError, match="closed"):
        await store.append(Event("third"))


def test_core_implementations_expose_runtime_contract_capabilities() -> None:
    """Keep runtime-checkable protocols aligned with shipped implementations."""
    bus = EventBus()

    assert isinstance(bus, EventBusContract)
    assert isinstance(bus.router, RouterContract)
    assert isinstance(bus.dispatcher, DispatcherContract)
    assert isinstance(JsonCodec(), Codec)
    assert isinstance(InMemoryEventStore(), EventStore)
    assert isinstance(InMemoryEventStore(), AsyncCloseable)


def test_json_codec_conforms_to_shared_requirements() -> None:
    """Validate the standard-library reference codec."""
    exercise_codec(JsonCodec())


def test_json_codec_is_deterministic() -> None:
    """Ensure set order does not affect encoded transport bytes."""
    codec = JsonCodec()
    left = Event("sample", tags={"z", "a"})
    right = Event("sample", tags={"a", "z"})

    assert codec.encode(left) == codec.encode(right)
    assert "sample" in codec.encode(left).decode("utf-8")


@pytest.mark.parametrize(
    "document",
    [
        b"not-json",
        b"[]",
        b'{"type":""}',
        b'{"type":1}',
        b'{"type":"sample","metadata":[]}',
        b'{"type":"sample","tags":[1]}',
    ],
)
def test_json_codec_rejects_invalid_event_documents(document: bytes) -> None:
    """Require malformed documents to fail at the codec boundary."""
    with pytest.raises(CodecError):
        JsonCodec().decode(document)


def test_json_codec_wraps_non_serializable_values() -> None:
    """Translate JSON serialization failures into the shared hierarchy."""
    with pytest.raises(CodecError, match="not JSON serializable"):
        JsonCodec().encode(Event("sample", payload=object()))


@pytest.mark.asyncio
async def test_in_memory_store_conforms_to_shared_requirements() -> None:
    """Validate the volatile reference store."""
    await exercise_event_store(InMemoryEventStore())


@pytest.mark.asyncio
@pytest.mark.parametrize("position", ["", "-1", "01", "position"])
async def test_in_memory_store_rejects_invalid_positions(position: str) -> None:
    """Expose invalid reference cursors as store boundary failures."""
    store = InMemoryEventStore()

    with pytest.raises(StoreError, match="position"):
        await collect(store, after=position)


@pytest.mark.asyncio
async def test_in_memory_store_async_context_owns_lifecycle() -> None:
    """Close the reference store on asynchronous context exit."""
    store = InMemoryEventStore()

    async with store:
        assert await store.append(Event("sample")) == "0"

    with pytest.raises(StoreError, match="closed"):
        await store.append(Event("later"))
