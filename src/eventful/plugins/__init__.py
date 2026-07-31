"""Experimental plugin namespace.

Plugins implement :class:`eventful.contracts.Plugin`; discovery and lifecycle
management are deferred to later 0.x releases.
"""
from __future__ import annotations
from eventful.api_status import ApiStatus
API_STATUS = ApiStatus.EXPERIMENTAL
__all__ = ["API_STATUS"]
