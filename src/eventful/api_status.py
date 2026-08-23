"""API stability markers used in docs and contracts."""
from __future__ import annotations
from enum import StrEnum

class ApiStatus(StrEnum):
    """Lifecycle labels for public namespaces and provisional contracts."""

    STABLE = "stable"
    PROVISIONAL = "provisional"
    EXPERIMENTAL = "experimental"
    INTERNAL = "internal"
