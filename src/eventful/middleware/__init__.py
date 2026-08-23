"""Provisional local listener-middleware chain.

Middleware wraps each selected listener in registration order. The first registered
middleware is outermost. Sync dispatch rejects awaitable middleware results, while
async dispatch awaits middleware and listener results sequentially.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from threading import RLock
from typing import Any

from eventful.api_status import ApiStatus
from eventful.contracts import EventHandler, Middleware
from eventful.event import Event
from eventful.exceptions import AsyncDispatchRequired


class MiddlewareChain:
    """Own a thread-safe ordered set of per-listener middleware."""

    def __init__(self, middleware: tuple[Middleware, ...] = ()) -> None:
        """Create a chain from middleware in outermost-first order."""
        self._middleware = list(middleware)
        self._lock = RLock()

    def add(self, middleware: Middleware) -> None:
        """Append a callable middleware if it is not already registered."""
        if not callable(middleware):
            raise TypeError("middleware must be callable")
        with self._lock:
            if middleware not in self._middleware:
                self._middleware.append(middleware)

    def remove(self, middleware: Middleware) -> bool:
        """Remove middleware and report whether it was registered."""
        with self._lock:
            if middleware not in self._middleware:
                return False
            self._middleware.remove(middleware)
            return True

    def snapshot(self) -> tuple[Middleware, ...]:
        """Return a stable outermost-first middleware snapshot."""
        with self._lock:
            return tuple(self._middleware)

    def requires_async(self) -> bool:
        """Report whether any registered middleware is declared async."""
        return any(
            inspect.iscoroutinefunction(item)
            or inspect.iscoroutinefunction(getattr(item, "__call__", None))
            for item in self.snapshot()
        )

    def invoke_sync(self, event: Event, handler: EventHandler) -> Any:
        """Invoke one listener through a snapshot, rejecting awaitable results."""
        call = handler
        for middleware in reversed(self.snapshot()):
            next_handler = call

            def call(
                current: Event,
                middleware: Middleware = middleware,
                next_handler: EventHandler = next_handler,
            ) -> Any:
                return middleware(current, next_handler)

        result = call(event)
        if inspect.isawaitable(result):
            close = getattr(result, "close", None)
            if close is not None:
                close()
            raise AsyncDispatchRequired(call)
        return result

    async def invoke_async(self, event: Event, handler: EventHandler) -> Any:
        """Invoke one listener through a snapshot and await its final result."""

        async def terminal(current: Event) -> Any:
            """Normalize the innermost listener into an async next-handler."""
            result = handler(current)
            if inspect.isawaitable(result):
                return await result
            return result

        call: EventHandler = terminal
        for middleware in reversed(self.snapshot()):
            next_handler = call

            async def call(
                current: Event,
                middleware: Middleware = middleware,
                next_handler: EventHandler = next_handler,
            ) -> Any:
                result = middleware(current, next_handler)
                if inspect.isawaitable(result):
                    return await result
                return result

        result: Any | Awaitable[Any] = call(event)
        if inspect.isawaitable(result):
            return await result
        return result


API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "MiddlewareChain"]
