"""Provisional framework adapter namespace.

Adapters are optional, component-specific, and keep application resource ownership
explicit instead of mutating the process-global bus.
"""

from __future__ import annotations
from eventful.api_status import ApiStatus

API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS"]
