"""Provisional v1 architectural contracts.

These Protocols define minimal seams for Eventful 0.x. They are importable with no
optional dependencies and are not yet stable API.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from typing import Any, Protocol, runtime_checkable
from eventful.event import Event

EventHandler = Callable[[Event], Any]

@runtime_checkable
class Publisher(Protocol):
    """Publishes events to a bus, broker, or stream."""
    def publish(self, event: Event) -> Awaitable[None] | None:
        """Publish one event, awaiting transport delivery when required."""
        ...

@runtime_checkable
class Consumer(Protocol):
    """Consumes events from a subscription."""
    def consume(self) -> AsyncIterator[Event]:
        """Yield events until cancellation or consumer shutdown."""
        ...

@runtime_checkable
class Subscription(Protocol):
    """Handle returned by subscribe operations."""
    topic: str
    def close(self) -> Awaitable[None] | None:
        """Release subscription resources idempotently."""
        ...

@runtime_checkable
class EventBusContract(Publisher, Protocol):
    """Local dispatch contract compatible with the legacy EventBus."""
    def register(self, topic: str, listener: EventHandler, **options: Any) -> None:
        """Register an in-process handler for a topic pattern."""
        ...
    def unregister(self, topic: str, listener: EventHandler) -> bool:
        """Remove one handler registration if present."""
        ...
    def emit_sync(self, event: Event) -> list[Any]:
        """Dispatch an event without accepting awaitable handlers."""
        ...
    def emit_async(self, event: Event) -> Awaitable[list[Any]]:
        """Dispatch an event and await awaitable handler results."""
        ...

@runtime_checkable
class RouterContract(Protocol):
    """Maps an event to interested handlers/subscriptions."""
    def get_listeners(self, event: Event) -> Iterable[EventHandler]:
        """Return handlers matching the event type and filters."""
        ...

@runtime_checkable
class DispatcherContract(Protocol):
    """Orders and invokes routed handlers."""
    def dispatch_order(self, listeners: Iterable[Any]) -> Iterable[Any]:
        """Return handlers in their configured invocation order."""
        ...

@runtime_checkable
class Middleware(Protocol):
    """Transforms or observes an event before/after dispatch."""
    def __call__(self, event: Event, next_handler: EventHandler) -> Any:
        """Observe or transform dispatch around the next handler."""
        ...

@runtime_checkable
class Codec(Protocol):
    """Encodes and decodes Event instances."""
    media_type: str
    def encode(self, event: Event) -> bytes:
        """Serialize an event into transport-safe bytes."""
        ...
    def decode(self, data: bytes) -> Event:
        """Deserialize bytes into an event or raise a codec error."""
        ...

@runtime_checkable
class EventStore(Protocol):
    """Append-only durable event storage seam."""
    def append(self, event: Event) -> Awaitable[str] | str:
        """Append one event and return its opaque position."""
        ...
    def read(self, *, after: str | None = None) -> AsyncIterator[Event]:
        """Yield events strictly after an optional opaque position."""
        ...

@runtime_checkable
class Transport(Protocol):
    """Broker/stream transport seam."""
    def publisher(self) -> Publisher:
        """Return the transport's publishing endpoint."""
        ...
    def consumer(self, topic: str) -> Consumer:
        """Return a consuming endpoint scoped to a topic."""
        ...

@runtime_checkable
class Plugin(Protocol):
    """Eventful extension entry point."""
    name: str
    def configure(self, settings: Mapping[str, Any]) -> None:
        """Apply validated settings before plugin use."""
        ...

@runtime_checkable
class ConfigurationSource(Protocol):
    """Loads configuration values."""
    def load(self) -> Mapping[str, Any]:
        """Load configuration without mutating global state."""
        ...

@runtime_checkable
class SchemaRegistry(Protocol):
    """Registers and resolves event schemas."""
    def register(self, event_type: str, schema: object) -> None:
        """Associate an event type with a schema object."""
        ...
    def resolve(self, event_type: str) -> object | None:
        """Resolve a schema or return ``None`` when unknown."""
        ...

@runtime_checkable
class ObservabilityProvider(Protocol):
    """Receives instrumentation callbacks."""
    def record_event(self, event: Event, attributes: Mapping[str, Any]) -> None:
        """Record event telemetry without changing dispatch behavior."""
        ...
