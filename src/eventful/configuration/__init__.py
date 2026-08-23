"""Provisional composable configuration-source implementations.

Sources return mappings and never mutate Eventful global configuration. Composition
uses explicit left-to-right precedence; conversion into `EventfulConfig` remains an
application decision through `EventfulConfig.from_mapping`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from eventful.api_status import ApiStatus


class MappingSource:
    """Expose a defensive snapshot of an application mapping."""

    def __init__(self, values: Mapping[str, Any]) -> None:
        """Copy source values so later caller mutation cannot affect loads."""
        self._values = dict(values)

    def load(self) -> Mapping[str, Any]:
        """Return an immutable copy owned by the caller."""
        return MappingProxyType(dict(self._values))


class EnvironmentSource:
    """Load prefixed environment variables as normalized lowercase keys."""

    def __init__(self, prefix: str = "EVENTFUL_") -> None:
        """Configure the prefix removed from matching variable names."""
        if not prefix:
            raise ValueError("prefix must not be empty")
        self.prefix = prefix

    def load(self) -> Mapping[str, Any]:
        """Snapshot matching environment strings without type conversion."""
        return MappingProxyType(
            {
                key.removeprefix(self.prefix).lower(): value
                for key, value in os.environ.items()
                if key.startswith(self.prefix)
            }
        )


class CompositeSource:
    """Merge configuration sources with later sources taking precedence."""

    def __init__(self, sources: Sequence[object]) -> None:
        """Capture an ordered, non-empty sequence of load-capable sources."""
        if not sources:
            raise ValueError("sources must not be empty")
        if any(not callable(getattr(source, "load", None)) for source in sources):
            raise TypeError("every configuration source must define load()")
        self.sources = tuple(sources)

    def load(self) -> Mapping[str, Any]:
        """Return a merged immutable mapping with explicit precedence."""
        merged: dict[str, Any] = {}
        for source in self.sources:
            merged.update(source.load())  # type: ignore[attr-defined]
        return MappingProxyType(merged)


API_STATUS = ApiStatus.PROVISIONAL
__all__ = [
    "API_STATUS",
    "CompositeSource",
    "EnvironmentSource",
    "MappingSource",
]
