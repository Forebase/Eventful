"""
Error handling for event listeners.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .event import Event


class ErrorHandler:
    """
    Handles errors that occur during event listener execution.
    """

    def __init__(self) -> None:
        self._handler: Callable[[BaseException, Event, Callable[..., Any]], None] | None = None

    def set_handler(
        self,
        handler: Callable[[BaseException, Event, Callable[..., Any]], None],
    ) -> None:
        """
        Set custom error handler.

        Parameters
        ----------
        handler : Callable[[BaseException, Event, Callable], None]
            Error handler function
        """
        self._handler = handler

    def handle_error(
        self, exc: BaseException, event: Event, listener: Callable[..., Any]
    ) -> None:
        """
        Handle an error from a listener.

        Parameters
        ----------
        exc : BaseException
            Exception that occurred
        event : Event
            Event being processed
        listener : Callable
            Listener that caused the error
        """
        if self._handler:
            self._handler(exc, event, listener)
        else:
            # Default behavior: log the error
            import logging
            logging.error(
                f"Error in listener {getattr(listener, '__name__', repr(listener))} "
                f"for event {event.type}: {exc}"
            )
