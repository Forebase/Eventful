"""
Listener registration and management.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from .event import Event

ListenerCallable = Callable[[Event], Any]
ListenerCallableT = TypeVar("ListenerCallableT", bound=ListenerCallable)


@dataclass
class ListenerConfig:
    """Configuration for a listener."""

    priority: int = 0
    tags: set[str] = field(default_factory=set)
    filter_fn: Callable[[Event], bool] | None = None
    once: bool = False


class Listener:
    """
    Wrapper for listener functions with configuration.
    """

    def __init__(self, func: ListenerCallable, config: ListenerConfig) -> None:
        self.func = func
        self.config = config

    def __call__(self, event: Event) -> Any:
        return self.func(event)

    def matches(self, event: Event) -> bool:
        """Check if this listener matches the given event."""
        # Check tags
        if self.config.tags and not self.config.tags.issubset(event.tags):
            return False

        # Check custom filter
        if self.config.filter_fn and not self.config.filter_fn(event):
            return False

        return True


def listener(
        topic: str | None = None,
        *,
        priority: int = 0,
        tags: Iterable[str] = (),
        filter: Callable[[Event], bool] | None = None,
        once: bool = False
) -> Callable[[ListenerCallableT], ListenerCallableT]:
    """
    Decorator to register a function as an event listener.

    Parameters
    ----------
    topic : str | None, optional
        Topic pattern to match. If None, uses function name.
    priority : int, optional
        Listener priority
    tags : Iterable[str], optional
        Required tags for events
    filter : Callable[[Event], bool] | None, optional
        Additional filter function
    once : bool, optional
        Unregister after first call

    Returns
    -------
    Callable
        Decorated function
    """

    def decorator(func: ListenerCallableT) -> ListenerCallableT:
        nonlocal topic
        if topic is None:
            topic = func.__name__

        from . import get_default_bus
        bus = get_default_bus()
        bus.register(topic, func, priority=priority, tags=tags, filter_fn=filter, once=once)

        return func

    return decorator
