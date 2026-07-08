"""
Framework adapters for eventful.
"""

from .fastapi import get_event_bus, add_eventful_middleware
from .starlette import request_event_bus, add_eventful_middleware

__all__ = [
    "get_event_bus",
    "add_eventful_middleware",
    "request_event_bus"
]
