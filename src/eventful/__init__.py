"""
Eventful - A universal event-bus / pub-sub system for microservice communication,
callbacks and general application-level event handling.
"""

from __future__ import annotations

import sys
from typing import Any, Callable, Iterable

from src.eventful.bus import EventBus, InMemoryBus
from src.eventful.config import EventfulConfig, get_config
from src.eventful.event import Event
from src.eventful.listener import Listener, listener
from src.eventful.stop_propagation import StopPropagation, stop_propagation

if sys.version_info < (3, 13):
    raise RuntimeError("eventful requires Python 3.13 or higher")

__version__ = "0.1.0"

# Global default bus instance
_default_bus: EventBus | None = None


def get_default_bus() -> EventBus:
    """Get or create the global default event bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = InMemoryBus(config=get_config())
    return _default_bus


def set_default_bus(bus: EventBus) -> None:
    """Set the global default event bus."""
    global _default_bus
    _default_bus = bus


def emit(event: Event | dict | Any, *, async_: bool | None = None) -> Any:
    """
    Emit an event to the default bus.

    Parameters
    ----------
    event : Event | dict | Any
        The event to emit. Can be an Event instance, dict, or any object with a type attribute.
    async_ : bool | None, optional
        Force async/sync mode. If None, auto-detects based on listeners.

    Returns
    -------
    Any
        List of listener results if sync, or awaitable if async.
    """
    return get_default_bus().emit(event, async_=async_)


# Re-export main API
__all__ = [
    "Event",
    "EventBus",
    "InMemoryBus",
    "Listener",
    "listener",
    "StopPropagation",
    "stop_propagation",
    "EventfulConfig",
    "get_config",
    "get_default_bus",
    "set_default_bus",
    "emit",
    "__version__",
]

# Optional imports for extras
try:
    from src.eventful.transports import RedisBus

    __all__.append("RedisBus")
except ImportError:
    pass

try:
    from src.eventful.persistence.file_persistence import FilePersistence

    __all__.append("FilePersistence")
except ImportError:
    pass

try:
    from src.eventful.persistence import PostgresPersistence

    __all__.append("PostgresPersistence")
except ImportError:
    pass

try:
    from src.eventful.adapters import get_event_bus

    __all__.append("get_event_bus")
except ImportError:
    pass

try:
    from src.eventful.adapters import request_event_bus

    __all__.append("request_event_bus")
except ImportError:
    pass

try:
    from src.eventful.utilities.rate_limit import rate_limit

    __all__.append("rate_limit")
except ImportError:
    pass

try:
    from src.eventful.utilities import debounce

    __all__.append("debounce")
except ImportError:
    pass

try:
    from src.eventful.utilities import EventfulLogHandler, emit_log

    __all__.extend(["EventfulLogHandler", "emit_log"])
except ImportError:
    pass
