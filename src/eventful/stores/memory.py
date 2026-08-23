"""Experimental in-memory event store for contract tests and examples."""
from __future__ import annotations
from collections.abc import AsyncIterator
from eventful.event import Event

class InMemoryEventStore:
    """Append-only volatile store; not durable and not process-safe."""
    def __init__(self) -> None:
        """Create an empty process-local append-only list."""
        self._events: list[tuple[str, Event]] = []
    def append(self, event: Event) -> str:
        """Append an event and return its zero-based string position."""
        position = str(len(self._events))
        self._events.append((position, event))
        return position
    async def read(self, *, after: str | None = None) -> AsyncIterator[Event]:
        """Yield a snapshot strictly after an optional string position."""
        start = int(after) + 1 if after is not None else 0
        for _, event in self._events[start:]:
            yield event
