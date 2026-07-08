"""
Event model implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """
    Base event class for eventful system.

    Attributes
    ----------
    type : str
        Hierarchical event type name (e.g., "service.user.created")
    payload : Any, optional
        User data associated with the event
    metadata : dict[str, Any]
        Additional metadata about the event
    tags : set[str]
        Optional tags for filtering events
    """

    type: str
    payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)

    _propagation_stopped: bool = field(default=False, init=False, repr=False)

    def stop_propagation(self) -> None:
        """Stop further propagation of this event to remaining listeners."""
        self._propagation_stopped = True

    @property
    def propagation_stopped(self) -> bool:
        """Check if propagation has been stopped for this event."""
        return self._propagation_stopped


def ensure_event(event: Event | dict | Any) -> Event:
    """
    Convert input to an Event instance if needed.

    Parameters
    ----------
    event : Event | dict | Any
        Input that can be an Event, dict, or any object

    Returns
    -------
    Event
        Proper Event instance
    """
    if isinstance(event, Event):
        return event
    elif isinstance(event, dict):
        return Event(**event)
    elif hasattr(event, 'type'):
        # Convert object with type attribute to Event
        payload = getattr(event, 'payload', None)
        metadata = getattr(event, 'metadata', {})
        tags = set(getattr(event, 'tags', []))
        return Event(type=str(event.type), payload=payload, metadata=metadata, tags=tags)
    else:
        # Treat as payload with inferred type
        return Event(type=type(event).__name__, payload=event)
