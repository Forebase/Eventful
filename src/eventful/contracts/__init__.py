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
    def publish(self, event: Event) -> Awaitable[None] | None: ...

@runtime_checkable
class Consumer(Protocol):
    """Consumes events from a subscription."""
    def consume(self) -> AsyncIterator[Event]: ...

@runtime_checkable
class Subscription(Protocol):
    """Handle returned by subscribe operations."""
    topic: str
    def close(self) -> Awaitable[None] | None: ...

@runtime_checkable
class EventBusContract(Publisher, Protocol):
    """Local dispatch contract compatible with the legacy EventBus."""
    def register(self, topic: str, listener: EventHandler, **options: Any) -> None: ...
    def unregister(self, topic: str, listener: EventHandler) -> bool: ...

@runtime_checkable
class RouterContract(Protocol):
    """Maps an event to interested handlers/subscriptions."""
    def get_listeners(self, event: Event) -> Iterable[EventHandler]: ...

@runtime_checkable
class DispatcherContract(Protocol):
    """Orders and invokes routed handlers."""
    def dispatch_order(self, listeners: Iterable[Any]) -> Iterable[Any]: ...

@runtime_checkable
class Middleware(Protocol):
    """Transforms or observes an event before/after dispatch."""
    def __call__(self, event: Event, next_handler: EventHandler) -> Any: ...

@runtime_checkable
class Codec(Protocol):
    """Encodes and decodes Event instances."""
    media_type: str
    def encode(self, event: Event) -> bytes: ...
    def decode(self, data: bytes) -> Event: ...

@runtime_checkable
class EventStore(Protocol):
    """Append-only durable event storage seam."""
    def append(self, event: Event) -> Awaitable[str] | str: ...
    def read(self, *, after: str | None = None) -> AsyncIterator[Event]: ...

@runtime_checkable
class Transport(Protocol):
    """Broker/stream transport seam."""
    def publisher(self) -> Publisher: ...
    def consumer(self, topic: str) -> Consumer: ...

@runtime_checkable
class Plugin(Protocol):
    """Eventful extension entry point."""
    name: str
    def configure(self, settings: Mapping[str, Any]) -> None: ...

@runtime_checkable
class ConfigurationSource(Protocol):
    """Loads configuration values."""
    def load(self) -> Mapping[str, Any]: ...

@runtime_checkable
class SchemaRegistry(Protocol):
    """Registers and resolves event schemas."""
    def register(self, event_type: str, schema: object) -> None: ...
    def resolve(self, event_type: str) -> object | None: ...

@runtime_checkable
class ObservabilityProvider(Protocol):
    """Receives instrumentation callbacks."""
    def record_event(self, event: Event, attributes: Mapping[str, Any]) -> None: ...
