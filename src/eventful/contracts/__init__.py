"""Provisional, dependency-free contracts for Eventful component boundaries.

Local dispatch is synchronous or asynchronous by explicit method. Boundaries that
may perform broker or storage I/O are uniformly asynchronous; implementations must
not return a mixture of immediate values and awaitables. Runtime-checkable protocols
support capability discovery, while conformance tests define behavioral semantics.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from typing import Any, Protocol, runtime_checkable

from eventful.event import Event

EventHandler = Callable[[Event], Any]


@runtime_checkable
class AsyncCloseable(Protocol):
    """Own asynchronous resources with an idempotent shutdown operation."""

    async def close(self) -> None:
        """Release owned resources; repeated calls must be harmless."""
        ...


@runtime_checkable
class Publisher(AsyncCloseable, Protocol):
    """Publish events across an asynchronous transport boundary."""

    async def publish(self, event: Event) -> None:
        """Publish one event or raise when delivery cannot be accepted."""
        ...


@runtime_checkable
class Subscription(AsyncCloseable, Protocol):
    """Own a topic subscription and its broker-side resources."""

    @property
    def topic(self) -> str:
        """Return the immutable topic associated with the subscription."""
        ...


@runtime_checkable
class Consumer(Subscription, Protocol):
    """Consume ordered events from one asynchronous subscription."""

    def consume(self) -> AsyncIterator[Event]:
        """Yield events until cancellation, failure, or subscription shutdown."""
        ...


@runtime_checkable
class EventBusContract(Protocol):
    """Register and dispatch handlers within the current process."""

    def register(
        self,
        topic: str,
        listener: EventHandler,
        priority: int = 0,
        tags: Iterable[str] = (),
        filter_fn: Callable[[Event], bool] | None = None,
        once: bool = False,
    ) -> None:
        """Register an in-process handler for a topic pattern."""
        ...

    def unregister(self, topic: str, listener: EventHandler) -> bool:
        """Remove the first matching handler registration if present."""
        ...

    def emit_sync(self, event: Event) -> list[Any]:
        """Dispatch without accepting awaitable handler results."""
        ...

    def emit_async(self, event: Event) -> Awaitable[list[Any]]:
        """Dispatch and await any awaitable handler results."""
        ...


@runtime_checkable
class RouterContract(Protocol):
    """Select registered listener objects for an event."""

    def get_listeners(self, event: Event) -> Iterable[Any]:
        """Return listener objects matching the event type and filters."""
        ...


@runtime_checkable
class DispatcherContract(Protocol):
    """Order listener objects without invoking them."""

    def dispatch_order(self, listeners: list[Any]) -> list[Any]:
        """Return listeners in their configured invocation order."""
        ...


@runtime_checkable
class Middleware(Protocol):
    """Transform or observe an event around the next local handler."""

    def __call__(self, event: Event, next_handler: EventHandler) -> Any:
        """Invoke middleware behavior and optionally call the next handler."""
        ...


@runtime_checkable
class Codec(Protocol):
    """Serialize complete public event values at transport/store boundaries."""

    @property
    def media_type(self) -> str:
        """Return the stable media type produced by this codec."""
        ...

    def encode(self, event: Event) -> bytes:
        """Serialize an event into transport-safe bytes."""
        ...

    def decode(self, data: bytes) -> Event:
        """Deserialize bytes or raise :class:`eventful.exceptions.CodecError`."""
        ...


@runtime_checkable
class EventStore(AsyncCloseable, Protocol):
    """Store immutable event snapshots behind opaque ordered positions."""

    async def append(self, event: Event) -> str:
        """Append one snapshot and return its opaque position."""
        ...

    def read(self, *, after: str | None = None) -> AsyncIterator[Event]:
        """Yield a read snapshot strictly after an optional position."""
        ...


@runtime_checkable
class Transport(AsyncCloseable, Protocol):
    """Create publishers and topic consumers sharing transport resources."""

    def publisher(self) -> Publisher:
        """Return a publisher whose lifecycle is explicit and idempotent."""
        ...

    def consumer(self, topic: str) -> Consumer:
        """Return a consumer scoped to a non-empty topic."""
        ...


@runtime_checkable
class Plugin(Protocol):
    """Configure a named Eventful extension before it is used."""

    @property
    def name(self) -> str:
        """Return the stable plugin identifier."""
        ...

    def configure(self, settings: Mapping[str, Any]) -> None:
        """Apply validated settings without mutating the input mapping."""
        ...


@runtime_checkable
class ConfigurationSource(Protocol):
    """Load configuration without changing Eventful global state."""

    def load(self) -> Mapping[str, Any]:
        """Return configuration values owned by the caller."""
        ...


@runtime_checkable
class SchemaRegistry(Protocol):
    """Associate event type names with application-owned schema objects."""

    def register(self, event_type: str, schema: object) -> None:
        """Associate a non-empty event type with a schema object."""
        ...

    def resolve(self, event_type: str) -> object | None:
        """Resolve a schema or return ``None`` when the type is unknown."""
        ...

    def validate(self, event: Event) -> None:
        """Validate a registered event or return when no schema exists."""
        ...


@runtime_checkable
class ObservabilityProvider(Protocol):
    """Receive telemetry without affecting dispatch outcomes."""

    def record_event(self, event: Event, attributes: Mapping[str, Any]) -> None:
        """Record event telemetry without mutating inputs."""
        ...


__all__ = [
    "AsyncCloseable",
    "Codec",
    "ConfigurationSource",
    "Consumer",
    "DispatcherContract",
    "EventBusContract",
    "EventHandler",
    "EventStore",
    "Middleware",
    "ObservabilityProvider",
    "Plugin",
    "Publisher",
    "RouterContract",
    "SchemaRegistry",
    "Subscription",
    "Transport",
]
