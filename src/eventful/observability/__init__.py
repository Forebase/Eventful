"""Experimental observability package for Eventful v1 topology.

This namespace intentionally exposes typed contracts and small in-memory helpers
only; production integrations will graduate through 0.x with explicit status.
"""
from __future__ import annotations

from eventful.api_status import ApiStatus

API_STATUS = ApiStatus.EXPERIMENTAL
__all__ = ["API_STATUS"]
