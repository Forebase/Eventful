"""Starlette-compatible ASGI request-state and lifespan integration.

The middleware attaches one application bus to HTTP/WebSocket scope state. A bus it
creates is adapter-owned; an injected bus is caller-owned unless shutdown ownership
is explicitly requested. No global default bus is mutated.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from eventful._optional import require_optional
from eventful.bus import EventBus, InMemoryBus

require_optional("Starlette adapter", "starlette", "starlette")


class EventfulMiddleware:
    """Attach an application bus to scopes and coordinate optional shutdown."""

    def __init__(
        self,
        app: Any,
        bus: EventBus | None = None,
        *,
        bus_factory: Callable[[], EventBus] | None = None,
        close_on_shutdown: bool | None = None,
        state_key: str = "eventful_bus",
    ) -> None:
        """Configure bus creation, ownership, state key, and lifespan cleanup."""
        if bus is not None and bus_factory is not None:
            raise ValueError("bus and bus_factory are mutually exclusive")
        if not state_key:
            raise ValueError("state_key must not be empty")
        self.app = app
        if bus is None:
            self.bus = bus_factory() if bus_factory is not None else InMemoryBus()
            owned = True
        else:
            self.bus = bus
            owned = False
        self.close_on_shutdown = (
            owned if close_on_shutdown is None else close_on_shutdown
        )
        self.state_key = state_key
        self._closed = False
        self._close_lock = asyncio.Lock()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Attach state and close owned resources when a lifespan terminates."""
        if scope["type"] in {"http", "websocket"}:
            scope.setdefault("state", {})[self.state_key] = self.bus

        if scope["type"] != "lifespan":
            await self.app(scope, receive, send)
            return

        async def lifespan_send(message: dict[str, Any]) -> None:
            """Close resources before reporting shutdown or failed startup."""
            if message["type"] in {
                "lifespan.startup.failed",
                "lifespan.shutdown.complete",
            }:
                await self.close()
            await send(message)

        try:
            await self.app(scope, receive, lifespan_send)
        except BaseException as application_error:
            # A lifespan exception may prevent the application from sending either
            # terminal message. Do not strand a bus that this adapter created.
            try:
                await self.close()
            except BaseException as cleanup_error:
                raise BaseExceptionGroup(
                    "lifespan application and Eventful cleanup failed",
                    [application_error, cleanup_error],
                ) from None
            raise

    async def close(self) -> None:
        """Close an owned/opted-in bus once when it exposes `close()`."""
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
        if not self.close_on_shutdown:
            return
        close = getattr(self.bus, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result


def request_event_bus(
    request: Any,
    *,
    state_key: str = "eventful_bus",
    default: EventBus | None = None,
) -> EventBus:
    """Resolve a request bus, optionally falling back to an explicit default."""
    bus = getattr(request.state, state_key, None)
    if bus is not None:
        return bus
    if default is not None:
        return default
    raise RuntimeError(
        f"request state has no {state_key!r}; install EventfulMiddleware first"
    )


def add_eventful_middleware(
    app: Any,
    bus: EventBus | None = None,
    **options: Any,
) -> None:
    """Install `EventfulMiddleware` on a Starlette-compatible application."""
    app.add_middleware(EventfulMiddleware, bus=bus, **options)


__all__ = ["EventfulMiddleware", "add_eventful_middleware", "request_event_bus"]
