"""Provisional schema validation and in-memory registry implementation.

Schemas validate local events before listener selection. This package defines no
serialization format or schema language; applications supply validator objects or
callables, while codecs remain responsible only for wire representation.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Protocol, cast, runtime_checkable

from eventful.api_status import ApiStatus
from eventful.event import Event
from eventful.exceptions import SchemaValidationError


@runtime_checkable
class EventSchema(Protocol):
    """Validate one event or raise a descriptive exception."""

    def validate(self, event: Event) -> None:
        """Accept a valid event or raise for invalid content."""
        ...


Schema = EventSchema | Callable[[Event], bool | None]


class InMemorySchemaRegistry:
    """Resolve exact event types to process-local schema validators."""

    def __init__(self) -> None:
        """Create an empty thread-safe registry."""
        self._schemas: dict[str, Schema] = {}
        self._lock = RLock()

    def register(self, event_type: str, schema: object) -> None:
        """Register or replace a validator for a non-empty exact event type."""
        if not event_type:
            raise ValueError("event_type must not be empty")
        if not callable(schema) and not isinstance(schema, EventSchema):
            raise TypeError("schema must be callable or implement EventSchema")
        with self._lock:
            self._schemas[event_type] = cast(Schema, schema)

    def unregister(self, event_type: str) -> bool:
        """Remove a schema and report whether it existed."""
        with self._lock:
            return self._schemas.pop(event_type, None) is not None

    def resolve(self, event_type: str) -> Schema | None:
        """Return the exact-type schema or `None` when unregistered."""
        with self._lock:
            return self._schemas.get(event_type)

    def validate(self, event: Event) -> None:
        """Validate an event when registered and normalize validation failures."""
        schema = self.resolve(event.type)
        if schema is None:
            return
        try:
            if isinstance(schema, EventSchema):
                schema.validate(event)
                result: bool | None = None
            else:
                result = schema(event)
            if result is False:
                raise ValueError("validator returned false")
        except SchemaValidationError:
            raise
        except Exception as exc:
            raise SchemaValidationError(
                f"event {event.type!r} failed schema validation: {exc}"
            ) from exc


API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "EventSchema", "InMemorySchemaRegistry", "Schema"]
