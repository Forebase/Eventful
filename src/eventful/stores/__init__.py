"""Provisional event-store contract implementations.

`InMemoryEventStore` is a volatile conformance reference. Durable storage,
cross-process coordination, and database migrations belong to persistence backends.
"""

from __future__ import annotations

from eventful.api_status import ApiStatus
from eventful.stores.memory import InMemoryEventStore

API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "InMemoryEventStore"]
