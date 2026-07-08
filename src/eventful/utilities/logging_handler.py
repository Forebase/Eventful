"""
Logging integration for eventful.
"""

from __future__ import annotations

import logging
import logging.handlers
from typing import Any, Optional

from ..event import Event
from .. import get_default_bus, emit

class EventfulLogHandler(logging.Handler):
    """
    Logging handler that emits log records as events.

    Converts log records to events with type "log.<levelname>" and
    includes log record attributes as metadata.
    """

    def __init__(self, bus=None, level=logging.NOTSET, include_extra: bool = True):
        """
        Initialize the logging handler.

        Parameters
        ----------
        bus : EventBus | None, optional
            Event bus to use. Defaults to global bus.
        level : int, optional
            Logging level threshold.
        include_extra : bool, optional
            Whether to include log record extra data in metadata.
        """
        super().__init__(level)
        self.bus = bus or get_default_bus()
        self.include_extra = include_extra

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record as an event.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to convert to event.
        """
        try:
            # Build metadata from log record
            metadata = {
                'name': record.name,
                'levelno': record.levelno,
                'levelname': record.levelname,
                'pathname': record.pathname,
                'filename': record.filename,
                'module': record.module,
                'lineno': record.lineno,
                'funcName': record.funcName,
                'created': record.created,
                'msecs': record.msecs,
                'relativeCreated': record.relativeCreated,
                'thread': record.thread,
                'threadName': record.threadName,
                'process': record.process,
                'processName': record.processName,
            }

            # Include extra fields if requested
            if self.include_extra and hasattr(record, '__dict__'):
                for key, value in record.__dict__.items():
                    if key not in metadata and not key.startswith('_'):
                        metadata[key] = value

            event = Event(
                type=f"log.{record.levelname.lower()}",
                payload=record.getMessage(),
                metadata=metadata
            )

            # Emit synchronously to avoid async complications in logging
            self.bus.emit(event, async_=False)

        except Exception:
            # Fall back to original logging if event emission fails
            self.handleError(record)

def emit_log(level: int, message: str, **extra: Any) -> None:
    """
    Emit a log message as an event directly.

    Parameters
    ----------
    level : int
        Logging level.
    message : str
        Log message.
    **extra : Any
        Additional metadata for the log event.
    """
    level_name = logging.getLevelName(level).lower()

    event = Event(
        type=f"log.{level_name}",
        payload=message,
        metadata=extra
    )

    emit(event)

def setup_logging_integration(
    bus=None,
    level: int = logging.INFO,
    include_extra: bool = True,
    propagate: bool = False
) -> EventfulLogHandler:
    """
    Set up eventful logging integration for the root logger.

    Parameters
    ----------
    bus : EventBus | None, optional
        Event bus to use.
    level : int, optional
        Logging level threshold.
    include_extra : bool, optional
        Whether to include extra data in metadata.
    propagate : bool, optional
        Whether to propagate to other handlers.

    Returns
    -------
    EventfulLogHandler
        The created logging handler.
    """
    handler = EventfulLogHandler(bus=bus, level=level, include_extra=include_extra)

    # Get root logger and add handler
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = propagate

    return handler

# Convenience functions for common log levels
def emit_debug(message: str, **extra: Any) -> None:
    """Emit a debug level log event."""
    emit_log(logging.DEBUG, message, **extra)

def emit_info(message: str, **extra: Any) -> None:
    """Emit an info level log event."""
    emit_log(logging.INFO, message, **extra)

def emit_warning(message: str, **extra: Any) -> None:
    """Emit a warning level log event."""
    emit_log(logging.WARNING, message, **extra)

def emit_error(message: str, **extra: Any) -> None:
    """Emit an error level log event."""
    emit_log(logging.ERROR, message, **extra)

def emit_critical(message: str, **extra: Any) -> None:
    """Emit a critical level log event."""
    emit_log(logging.CRITICAL, message, **extra)
