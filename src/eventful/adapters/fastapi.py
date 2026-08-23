"""Experimental FastAPI dependency-injection boundary.

This module only resolves an explicitly provided or process-default local bus.
Application lifespan ownership and request-scoped buses remain deferred.
"""
from __future__ import annotations

from eventful._optional import require_optional
from eventful.bus import EventBus


def get_event_bus(bus: EventBus | None = None) -> EventBus:
    """Return an EventBus for FastAPI dependency injection examples."""
    require_optional("FastAPI adapter", "fastapi", "fastapi")
    if bus is not None:
        return bus
    from eventful import get_default_bus

    return get_default_bus()
