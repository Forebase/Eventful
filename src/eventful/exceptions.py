"""Shared exceptions crossing Eventful component boundaries."""

from __future__ import annotations
from collections.abc import Callable
from typing import Any
from ._optional import OptionalDependencyError as OptionalDependencyError


class EventfulError(Exception):
    """Base class for Eventful errors."""


class ConfigurationError(EventfulError):
    """Invalid configuration or configuration source failure."""


class ContractError(EventfulError):
    """A component violated a documented Eventful contract."""


class CodecError(EventfulError):
    """Event encoding or decoding failed."""


class StoreError(EventfulError):
    """Durable event storage failed."""


class TransportError(EventfulError):
    """Broker transport operation or incoming message validation failed."""


class AsyncDispatchRequired(EventfulError):
    """Raised when synchronous dispatch encounters an awaitable listener."""

    def __init__(self, listener: Callable[..., Any]) -> None:
        """Describe the listener that requires :meth:`EventBus.emit_async`."""
        super().__init__(
            f"listener {listener!r} requires asynchronous dispatch; "
            "use 'await bus.emit_async(event)'"
        )
        self.listener = listener
