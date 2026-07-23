"""Framework adapter namespace.

Adapters are optional and must be imported component-by-component.
"""
from __future__ import annotations
from eventful.api_status import ApiStatus
API_STATUS = ApiStatus.EXPERIMENTAL
__all__ = ["API_STATUS"]
