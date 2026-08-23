"""FastAPI installation and dependency helpers built on the ASGI adapter.

FastAPI applications share the Starlette middleware lifecycle and request-state
boundary. Helpers never mutate Eventful's process-global default bus.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from eventful._optional import require_optional
from eventful.adapters.starlette import add_eventful_middleware, request_event_bus
from eventful.bus import EventBus

_fastapi = require_optional("FastAPI adapter", "fastapi", "fastapi")


def get_event_bus(
    request: Any | None = None,
    bus: EventBus | None = None,
) -> EventBus:
    """Resolve an explicit bus, request-state bus, or compatibility default."""
    if bus is not None:
        return bus
    if request is not None:
        return request_event_bus(request)
    from eventful import get_default_bus

    return get_default_bus()


def event_bus_dependency(
    bus: EventBus | None = None,
    *,
    state_key: str = "eventful_bus",
) -> Callable[[Any], EventBus]:
    """Create a FastAPI dependency resolving an explicit or request-state bus."""

    def dependency(request: Any) -> EventBus:
        """Resolve the bus for one dependency invocation."""
        if bus is not None:
            return bus
        return request_event_bus(request, state_key=state_key)

    dependency.__annotations__["request"] = _fastapi.Request
    return dependency


def install_eventful(
    app: Any,
    bus: EventBus | None = None,
    **options: Any,
) -> None:
    """Install Eventful's request-state and lifespan middleware on FastAPI."""
    add_eventful_middleware(app, bus=bus, **options)


__all__ = ["event_bus_dependency", "get_event_bus", "install_eventful"]
