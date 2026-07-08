"""
Event bus implementations.
"""

from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict, deque
from threading import RLock
from typing import Any, Awaitable, Callable, Iterable, List, Optional

from .config import EventfulConfig
from .dispatch import Dispatcher
from .event import Event, ensure_event
from listener import Listener, ListenerConfig
from router import Router

import logging as log

class EventBus:
    """
    Base class for event bus implementations.

    This provides the core event handling functionality that can be extended
    by specific transport implementations.
    """

    def __init__(self, config: EventfulConfig | None = None):
        """
        Initialize event bus.

        Parameters
        ----------
        config : EventfulConfig | None
            Configuration for this bus instance
        """
        self.config = config or EventfulConfig()
        self.router = Router()
        self.dispatcher = Dispatcher(
            enable_priorities=self.config.enable_priorities,
            propagation_enabled=self.config.propagation_enabled
        )
        self._listeners: dict[str, List[Listener]] = defaultdict(list)
        self._lock = RLock()
        self._error_handler: Optional[Callable[[BaseException, Event, Callable], None]] = None

    def set_error_handler(self, handler: Callable[[BaseException, Event, Callable], None]) -> None:
        """
        Set custom error handler for listener exceptions.

        Parameters
        ----------
        handler : Callable[[BaseException, Event, Callable], None]
            Error handler function
        """
        self._error_handler = handler

    def register(
            self,
            topic: str,
            listener: Callable,
            priority: int = 0,
            tags: Iterable[str] = (),
            filter_fn: Optional[Callable[[Event], bool]] = None,
            once: bool = False
    ) -> None:
        """
        Register a listener for events matching the given criteria.

        Parameters
        ----------
        topic : str
            Topic pattern to match
        listener : Callable
            Listener function/callable
        priority : int, optional
            Listener priority (higher = executed first)
        tags : Iterable[str], optional
            Tags that must be present in event
        filter_fn : Callable[[Event], bool] | None, optional
            Additional filter function
        once : bool, optional
            Whether to unregister after first call
        """
        listener_config = ListenerConfig(
            priority=priority,
            tags=set(tags),
            filter_fn=filter_fn,
            once=once
        )

        with self._lock:
            log.info(f"Registering event listener ('{listener}') on: {topic}")
            listener_obj = Listener(listener, listener_config)
            self._listeners[topic].append(listener_obj)
            self.router.add_listener(topic, listener_obj)


    def unregister(self, topic: str, listener: Callable) -> bool:
        """
        Unregister a listener from a topic.

        Parameters
        ----------
        topic : str
            Topic pattern
        listener : Callable
            Listener function to remove

        Returns
        -------
        bool
            True if listener was found and removed
        """
        log.info(f"Deregistering event listener ('{listener}') on: {topic}")
        with self._lock:
            if topic not in self._listeners:
                return False

            listener_obj = None
            for l in self._listeners[topic]:
                if l.func == listener:
                    listener_obj = l
                    break

            if listener_obj:
                self._listeners[topic].remove(listener_obj)
                self.router.remove_listener(topic, listener_obj)
                return True

            return False

    def emit(self, event: Event | dict | Any, *, async_: bool | None = None) -> Any:
        """
        Emit an event to all matching listeners.

        Parameters
        ----------
        event : Event | dict | Any
            Event to emit
        async_ : bool | None, optional
            Force async/sync mode

        Returns
        -------
        Any
            List of results if sync, awaitable if async
        """
        log.debug(f"Emitting event: {event}")
        event_obj = ensure_event(event)
        listeners = self.router.get_listeners(event_obj)

        if not listeners:
            return [] if async_ is False else asyncio.sleep(0, result=[])

        # Check if we need async mode
        has_async = any(inspect.iscoroutinefunction(l.func) for l in listeners)
        use_async = async_ if async_ is not None else has_async

        if use_async:
            return self._emit_async(event_obj, listeners)
        else:
            return self._emit_sync(event_obj, listeners)

    def _emit_sync(self, event: Event, listeners: List[Listener]) -> List[Any]:
        """Emit event synchronously."""
        results = []
        for listener in self.dispatcher.dispatch_order(listeners):
            if event.propagation_stopped:
                break

            try:
                result = listener(event)
                results.append(result)

                if listener.config.once:
                    self.unregister(self._find_topic_for_listener(listener), listener.func)

            except Exception as exc:
                if self._error_handler:
                    self._error_handler(exc, event, listener.func)
                else:
                    # Default behavior: log and continue
                    import logging
                    logging.error(f"Error in listener {listener.func}: {exc}")

        return results

    async def _emit_async(self, event: Event, listeners: List[Listener]) -> List[Any]:
        """Emit event asynchronously."""
        results = []
        for listener in self.dispatcher.dispatch_order(listeners):
            if event.propagation_stopped:
                break

            try:
                if inspect.iscoroutinefunction(listener.func):
                    result = await listener.func(event)
                else:
                    result = listener.func(event)
                results.append(result)

                if listener.config.once:
                    self.unregister(self._find_topic_for_listener(listener), listener.func)

            except Exception as exc:
                if self._error_handler:
                    self._error_handler(exc, event, listener.func)
                else:
                    # Default behavior: log and continue
                    import logging
                    logging.error(f"Error in listener {listener.func}: {exc}")

        return results

    def _find_topic_for_listener(self, listener: Listener) -> str:
        """Find the topic that a listener is registered under."""
        with self._lock:
            for topic, listeners in self._listeners.items():
                if listener in listeners:
                    return topic
        raise ValueError("Listener not found")


class InMemoryBus(EventBus):
    """
    In-memory event bus implementation.

    This is the default bus implementation that operates entirely in memory
    with thread-safe operations.
    """

    def __init__(self, config: EventfulConfig | None = None):
        super().__init__(config)
        self._event_queue = deque()
        self._processing = False

    def emit(self, event: Event | dict | Any, *, async_: bool | None = None) -> Any:
        """
        Emit event with optional queueing for thread safety.
        """
        event_obj = ensure_event(event)

        if self._processing:
            # If we're already processing, queue the event
            self._event_queue.append((event_obj, async_))
            return [] if async_ is False else asyncio.sleep(0, result=[])

        self._processing = True
        try:
            result = super().emit(event_obj, async_=async_)

            # Process queued events
            while self._event_queue:
                queued_event, queued_async = self._event_queue.popleft()
                super().emit(queued_event, async_=queued_async)

            return result
        finally:
            self._processing = False
