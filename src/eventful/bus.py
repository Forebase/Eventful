"""Synchronous and asynchronous local event-bus implementations.

This module owns listener registration and in-process dispatch only. Broker
delivery and durable storage belong to :mod:`eventful.transports` and
:mod:`eventful.persistence`; the local bus never performs network or disk I/O.
"""

from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable
from threading import RLock
from typing import Any

from .config import EventfulConfig
from .contracts import Middleware, ObservabilityProvider, SchemaRegistry
from .dispatch import Dispatcher
from .event import Event, ensure_event
from .exceptions import AsyncDispatchRequired
from .listener import Listener, ListenerCallable, ListenerConfig
from .middleware import MiddlewareChain
from .router import Router

ErrorHandler = Callable[[BaseException, Event, ListenerCallable], None]
EventInput = Event | dict[str, Any] | Any


class EventBus:
    """Route events to a snapshot of registered in-process listeners.

    Registration and listener snapshots are protected by a re-entrant lock.
    The lock is never held while application callbacks execute, so listeners may
    emit, register, or unregister recursively. Nested emissions are depth-first:
    the nested event completes before dispatch resumes at the next outer listener.

    Listener failures are logged and dispatch continues unless a custom error
    handler raises. Results contain successful listener return values only.
    """

    def __init__(
        self,
        config: EventfulConfig | None = None,
        *,
        middleware: Iterable[Middleware] = (),
        schema_registry: SchemaRegistry | None = None,
        observability: Iterable[ObservabilityProvider] = (),
    ) -> None:
        """Initialize an empty bus with an isolated configuration object."""
        self.config = config or EventfulConfig()
        self.router = Router()
        self.dispatcher = Dispatcher(
            enable_priorities=self.config.enable_priorities,
            propagation_enabled=self.config.propagation_enabled,
        )
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._lock = RLock()
        self._error_handler: ErrorHandler | None = None
        self.middleware = MiddlewareChain(tuple(middleware))
        self.schema_registry = schema_registry
        self._observability = list(observability)

    def set_error_handler(self, handler: ErrorHandler | None) -> None:
        """Set the listener-failure callback, or restore logging with ``None``.

        The callback receives the exception, event, and original listener. If the
        callback itself raises, that exception stops and escapes dispatch.
        """
        self._error_handler = handler

    def add_middleware(self, middleware: Middleware) -> None:
        """Append per-listener middleware in outermost-first order."""
        self.middleware.add(middleware)

    def remove_middleware(self, middleware: Middleware) -> bool:
        """Remove middleware and report whether it was registered."""
        return self.middleware.remove(middleware)

    def add_observability_provider(self, provider: ObservabilityProvider) -> None:
        """Register a best-effort provider if it is not already present."""
        if not isinstance(provider, ObservabilityProvider):
            raise TypeError("provider must implement ObservabilityProvider")
        with self._lock:
            if provider not in self._observability:
                self._observability.append(provider)

    def remove_observability_provider(self, provider: ObservabilityProvider) -> bool:
        """Remove an observability provider and report whether it existed."""
        with self._lock:
            if provider not in self._observability:
                return False
            self._observability.remove(provider)
            return True

    def set_schema_registry(self, registry: SchemaRegistry | None) -> None:
        """Set or disable validation performed before listener selection."""
        if registry is not None and not isinstance(registry, SchemaRegistry):
            raise TypeError("registry must implement SchemaRegistry")
        self.schema_registry = registry

    def register(
        self,
        topic: str,
        listener: ListenerCallable,
        priority: int = 0,
        tags: Iterable[str] = (),
        filter_fn: Callable[[Event], bool] | None = None,
        once: bool = False,
    ) -> None:
        """Register ``listener`` for a topic pattern.

        ``*`` matches one topic segment and ``**`` matches the remaining suffix.
        Required ``tags`` and ``filter_fn`` are evaluated while routing. Duplicate
        registrations are permitted and are invoked independently.
        """
        if not topic:
            raise ValueError("topic must not be empty")
        if not callable(listener):
            raise TypeError("listener must be callable")

        registered = Listener(
            listener,
            ListenerConfig(
                priority=priority,
                tags=set(tags),
                filter_fn=filter_fn,
                once=once,
            ),
        )
        with self._lock:
            self._listeners[topic].append(registered)
            self.router.add_listener(topic, registered)

    def unregister(self, topic: str, listener: ListenerCallable) -> bool:
        """Remove the first matching registration and report whether it existed."""
        with self._lock:
            for registered in self._listeners.get(topic, ()):
                if registered.func == listener:
                    return self._remove_registration(topic, registered)
        return False

    def emit(
        self, event: EventInput, *, async_: bool | None = None
    ) -> list[Any] | Awaitable[list[Any]]:
        """Dispatch using compatibility-mode automatic async detection.

        ``async_=False`` delegates to :meth:`emit_sync`, ``async_=True`` delegates
        to :meth:`emit_async`, and the default returns an awaitable only when a
        registered listener is declared with ``async def``. Prefer the explicit
        methods in new code because a regular function may dynamically return an
        awaitable that automatic detection cannot predict.
        """
        event_obj = ensure_event(event)
        self._validate_event(event_obj)
        listeners = self._listener_snapshot(event_obj)
        use_async = (
            any(inspect.iscoroutinefunction(item.func) for item in listeners)
            or self.middleware.requires_async()
            if async_ is None
            else async_
        )
        if use_async:
            return self._emit_async(event_obj, listeners)
        return self._emit_sync(event_obj, listeners)

    def emit_sync(self, event: EventInput) -> list[Any]:
        """Dispatch synchronously and return successful listener results.

        An :class:`AsyncDispatchRequired` error is raised before invoking a
        declared async listener. A dynamically returned awaitable is closed when
        possible and raises the same error rather than leaking a coroutine.
        """
        event_obj = ensure_event(event)
        self._validate_event(event_obj)
        return self._emit_sync(event_obj, self._listener_snapshot(event_obj))

    async def emit_async(self, event: EventInput) -> list[Any]:
        """Dispatch in registration order, awaiting every awaitable result."""
        event_obj = ensure_event(event)
        self._validate_event(event_obj)
        return await self._emit_async(event_obj, self._listener_snapshot(event_obj))

    def _listener_snapshot(self, event: Event) -> list[Listener]:
        """Return matching listeners without retaining the registration lock."""
        with self._lock:
            return list(self.router.get_listeners(event))

    def _emit_sync(self, event: Event, listeners: list[Listener]) -> list[Any]:
        """Invoke a previously captured listener snapshot synchronously."""
        results: list[Any] = []
        self._observe(
            event,
            {
                "stage": "dispatch.started",
                "mode": "sync",
                "listener_count": len(listeners),
            },
        )
        try:
            for registered in self.dispatcher.dispatch_order(listeners):
                if self._should_stop(event):
                    break
                if inspect.iscoroutinefunction(registered.func):
                    raise AsyncDispatchRequired(registered.func)
                if not self._claim_once(registered):
                    continue
                try:
                    result = self.middleware.invoke_sync(event, registered.func)
                    results.append(result)
                except AsyncDispatchRequired:
                    raise
                except Exception as exc:
                    self._handle_error(exc, event, registered.func)
        except Exception as exc:
            self._observe(
                event,
                {
                    "stage": "dispatch.failed",
                    "mode": "sync",
                    "error_type": type(exc).__name__,
                },
            )
            raise
        self._observe(
            event,
            {
                "stage": "dispatch.completed",
                "mode": "sync",
                "result_count": len(results),
            },
        )
        return results

    async def _emit_async(self, event: Event, listeners: list[Listener]) -> list[Any]:
        """Invoke a previously captured listener snapshot asynchronously."""
        results: list[Any] = []
        self._observe(
            event,
            {
                "stage": "dispatch.started",
                "mode": "async",
                "listener_count": len(listeners),
            },
        )
        try:
            for registered in self.dispatcher.dispatch_order(listeners):
                if self._should_stop(event):
                    break
                if not self._claim_once(registered):
                    continue
                try:
                    result = await self.middleware.invoke_async(event, registered.func)
                    results.append(result)
                except Exception as exc:
                    self._handle_error(exc, event, registered.func)
        except Exception as exc:
            self._observe(
                event,
                {
                    "stage": "dispatch.failed",
                    "mode": "async",
                    "error_type": type(exc).__name__,
                },
            )
            raise
        self._observe(
            event,
            {
                "stage": "dispatch.completed",
                "mode": "async",
                "result_count": len(results),
            },
        )
        return results

    def _validate_event(self, event: Event) -> None:
        """Validate through the configured registry before routing."""
        if self.schema_registry is None:
            return
        try:
            self.schema_registry.validate(event)
        except Exception as exc:
            self._observe(
                event, {"stage": "schema.failed", "error_type": type(exc).__name__}
            )
            raise

    def _should_stop(self, event: Event) -> bool:
        """Apply propagation state only when propagation control is enabled."""
        return self.dispatcher.propagation_enabled and event.propagation_stopped

    def _claim_once(self, registered: Listener) -> bool:
        """Atomically claim a once-listener, returning false if already claimed."""
        if not registered.config.once:
            return True
        with self._lock:
            topic = self._find_topic_for_listener(registered)
            if topic is None:
                return False
            return self._remove_registration(topic, registered)

    def _find_topic_for_listener(self, registered: Listener) -> str | None:
        """Find the topic owning a listener while the caller holds ``_lock``."""
        for topic, listeners in self._listeners.items():
            if registered in listeners:
                return topic
        return None

    def _remove_registration(self, topic: str, registered: Listener) -> bool:
        """Remove a known registration while the caller holds ``_lock``."""
        listeners = self._listeners.get(topic)
        if listeners is None or registered not in listeners:
            return False
        listeners.remove(registered)
        self.router.remove_listener(topic, registered)
        if not listeners:
            del self._listeners[topic]
        return True

    def _handle_error(
        self, exc: BaseException, event: Event, listener: ListenerCallable
    ) -> None:
        """Invoke the custom failure policy or log and continue by default."""
        self._observe(
            event,
            {"stage": "listener.failed", "error_type": type(exc).__name__},
        )
        if self._error_handler is not None:
            self._error_handler(exc, event, listener)
            return
        logging.getLogger(__name__).exception(
            "Error in listener %r for event %s",
            listener,
            event.type,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    def _observe(self, event: Event, attributes: dict[str, Any]) -> None:
        """Record best-effort signals without changing dispatch outcomes."""
        with self._lock:
            providers = tuple(self._observability)
        for provider in providers:
            try:
                provider.record_event(event, attributes)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Observability provider %r failed for event %s",
                    provider,
                    event.type,
                )


class InMemoryBus(EventBus):
    """Default local bus retained as an explicit backend name.

    It currently adds no behavior to :class:`EventBus`; the subclass exists to
    distinguish local dispatch from future transport-backed bus implementations.
    Events and registrations remain process-local and are never persisted.
    """
