"""In-memory reference implementation of the provisional event-store contract.

The store is intended for conformance tests and local examples, not durability. It
uses decimal positions, copies values across its boundary, supports concurrent
threads, and exposes the same asynchronous lifecycle as future durable stores.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from copy import deepcopy
from threading import RLock

from eventful.event import Event
from eventful.exceptions import StoreError


class InMemoryEventStore:
    """Append and read isolated event snapshots in process memory."""

    def __init__(self) -> None:
        """Create an open, empty, thread-safe store."""
        self._events: list[Event] = []
        self._lock = RLock()
        self._closed = False

    async def append(self, event: Event) -> str:
        """Append a deep copy and return its zero-based decimal position."""
        if not isinstance(event, Event):
            raise TypeError("event must be an Event")
        with self._lock:
            self._ensure_open()
            try:
                snapshot = deepcopy(event)
            except Exception as exc:
                raise StoreError("event could not be copied") from exc
            position = str(len(self._events))
            self._events.append(snapshot)
            return position

    async def read(self, *, after: str | None = None) -> AsyncIterator[Event]:
        """Yield copied events from a stable snapshot after ``after``."""
        start = self._parse_position(after)
        with self._lock:
            self._ensure_open()
            try:
                snapshot = deepcopy(self._events[start:])
            except Exception as exc:
                raise StoreError("stored events could not be copied") from exc
        for event in snapshot:
            yield event

    async def close(self) -> None:
        """Close the store idempotently and retain data for garbage collection."""
        with self._lock:
            self._closed = True

    async def __aenter__(self) -> InMemoryEventStore:
        """Return the open store for asynchronous context management."""
        with self._lock:
            self._ensure_open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Close the store when leaving an asynchronous context."""
        await self.close()

    def _parse_position(self, after: str | None) -> int:
        """Translate an opaque reference position into a slice start."""
        if after is None:
            return 0
        try:
            position = int(after)
        except (TypeError, ValueError) as exc:
            raise StoreError(f"invalid event position: {after!r}") from exc
        if position < 0 or str(position) != after:
            raise StoreError(f"invalid event position: {after!r}")
        return position + 1

    def _ensure_open(self) -> None:
        """Reject operations after lifecycle shutdown."""
        if self._closed:
            raise StoreError("event store is closed")
