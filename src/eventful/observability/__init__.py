"""Provisional dependency-free observability providers.

Providers receive best-effort dispatch signals from the local bus. Instrumentation
must not alter application outcomes; provider failures are logged and isolated by
the bus. This package does not prescribe an external telemetry vendor or protocol.
"""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Any

from eventful.api_status import ApiStatus
from eventful.event import Event


@dataclass(frozen=True)
class Observation:
    """Immutable snapshot of one event instrumentation signal."""

    event_type: str
    attributes: MappingProxyType[str, Any]


class InMemoryObservabilityProvider:
    """Collect observation snapshots for tests and local diagnostics."""

    def __init__(self) -> None:
        """Create an empty thread-safe observation buffer."""
        self._records: list[Observation] = []
        self._lock = RLock()

    def record_event(self, event: Event, attributes: Mapping[str, Any]) -> None:
        """Copy an event type and attributes without retaining mutable inputs."""
        snapshot = Observation(
            event_type=event.type,
            attributes=MappingProxyType(deepcopy(dict(attributes))),
        )
        with self._lock:
            self._records.append(snapshot)

    @property
    def records(self) -> tuple[Observation, ...]:
        """Return a stable snapshot of recorded signals."""
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        """Remove all buffered signals."""
        with self._lock:
            self._records.clear()


API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "InMemoryObservabilityProvider", "Observation"]
