"""Public facade for Eventful 0.2.

The root API preserves the 0.1 local in-memory dispatcher pattern. Broader v1
contracts live under :mod:`eventful.contracts` and are provisional; experimental
integrations are intentionally not imported here so minimal installs stay clean.
"""
from __future__ import annotations

import sys
from typing import Any

from eventful.__version__ import __version__
from eventful.bus import EventBus, InMemoryBus
from eventful.config import EventfulConfig, get_config, set_config
from eventful.event import Event, ensure_event
from eventful.exceptions import (
    AsyncDispatchRequired,
    EventfulError,
    OptionalDependencyError,
)
from eventful.listener import Listener, listener
from eventful.stop_propagation import StopPropagation, stop_propagation

if sys.version_info < (3, 13):
    raise RuntimeError("eventful requires Python 3.13 or higher")

_default_bus: EventBus | None = None

def get_default_bus() -> EventBus:
    """Return the process-local default in-memory event bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = InMemoryBus(config=get_config())
    return _default_bus

def set_default_bus(bus: EventBus) -> None:
    """Replace the process-local default bus."""
    global _default_bus
    _default_bus = bus

def emit(event: Event | dict[str, Any] | Any, *, async_: bool | None = None) -> Any:
    """Dispatch through the default bus using compatibility async detection."""
    return get_default_bus().emit(event, async_=async_)


def emit_sync(event: Event | dict[str, Any] | Any) -> list[Any]:
    """Dispatch synchronously through the process-local default bus."""
    return get_default_bus().emit_sync(event)


async def emit_async(event: Event | dict[str, Any] | Any) -> list[Any]:
    """Dispatch asynchronously through the process-local default bus."""
    return await get_default_bus().emit_async(event)

__all__ = [
    "Event", "ensure_event", "EventBus", "InMemoryBus", "Listener", "listener",
    "StopPropagation", "stop_propagation", "EventfulConfig", "get_config",
    "set_config", "get_default_bus", "set_default_bus", "emit", "emit_sync",
    "emit_async", "EventfulError", "AsyncDispatchRequired",
    "OptionalDependencyError", "__version__",
]
