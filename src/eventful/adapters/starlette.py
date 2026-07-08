"""
Starlette adapter for eventful.
"""

from __future__ import annotations

from typing import Optional

try:
    from starlette.requests import Request
    from starlette.types import ASGIApp, Receive, Scope, Send
except ImportError:
    raise ImportError("Starlette adapter requires 'starlette' package. Install with 'pip install eventful[starlette]'")

from src.eventful.bus import EventBus, get_default_bus


class EventfulMiddleware:
    """
    Starlette middleware for event bus integration.
    """

    def __init__(self, app: ASGIApp, bus: Optional[EventBus] = None):
        self.app = app
        self.bus = bus or get_default_bus()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            request.state.event_bus = self.bus

        await self.app(scope, receive, send)


def request_event_bus(request: Request) -> EventBus:
    """
    Get event bus from Starlette request state.

    Parameters
    ----------
    request : Request
        Starlette request.

    Returns
    -------
    EventBus
        Event bus instance.
    """
    return getattr(request.state, 'event_bus', get_default_bus())


def add_eventful_middleware(app: ASGIApp, bus: Optional[EventBus] = None) -> None:
    """
    Add eventful middleware to Starlette app.

    Parameters
    ----------
    app : ASGIApp
        Starlette application.
    bus : EventBus | None, optional
        Event bus instance to use.
    """
    app.add_middleware(EventfulMiddleware, bus=bus)
