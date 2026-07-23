"""Experimental Starlette middleware helpers."""
from __future__ import annotations

from typing import Any

from eventful._optional import require_optional
from eventful.bus import EventBus

_starlette_requests = require_optional("Starlette adapter", "starlette", "starlette.requests")
_starlette_types = require_optional("Starlette adapter", "starlette", "starlette.types")
Request = _starlette_requests.Request
ASGIApp = _starlette_types.ASGIApp
Receive = _starlette_types.Receive
Scope = _starlette_types.Scope
Send = _starlette_types.Send

class EventfulMiddleware:
    """Attach an Eventful bus to Starlette request state."""
    def __init__(self, app: ASGIApp, bus: EventBus | None = None) -> None:
        self.app = app
        if bus is None:
            from eventful import get_default_bus
            bus = get_default_bus()
        self.bus = bus
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            request.state.event_bus = self.bus
        await self.app(scope, receive, send)

def request_event_bus(request: Any) -> EventBus:
    """Return the bus attached to request state, or the default bus."""
    from eventful import get_default_bus
    return getattr(request.state, "event_bus", get_default_bus())

def add_eventful_middleware(app: Any, bus: EventBus | None = None) -> None:
    """Install EventfulMiddleware on a Starlette-compatible app."""
    app.add_middleware(EventfulMiddleware, bus=bus)
