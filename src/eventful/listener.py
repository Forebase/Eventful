"""
Listener registration and management.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Set


@dataclass
class ListenerConfig:
    """Configuration for a listener."""

    priority: int = 0
    tags: Set[str] = None  # type: ignore
    filter_fn: Optional[Callable[[Any], bool]] = None
    once: bool = False

    def __post_init__(self):
        if self.tags is None:
            self.tags = set()


class Listener:
    """
    Wrapper for listener functions with configuration.
    """

    def __init__(self, func: Callable, config: ListenerConfig):
        self.func = func
        self.config = config

    def __call__(self, event: Any) -> Any:
        return self.func(event)

    def matches(self, event: Any) -> bool:
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
        filter: Optional[Callable[[Any], bool]] = None,
        once: bool = False
) -> Callable:
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

    def decorator(func: Callable) -> Callable:
        nonlocal topic
        if topic is None:
            topic = func.__name__

        from . import get_default_bus
        bus = get_default_bus()
        bus.register(topic, func, priority=priority, tags=tags, filter_fn=filter, once=once)

        return func

    return decorator
