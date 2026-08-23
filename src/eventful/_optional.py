"""Helpers for optional dependency boundaries."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType


class OptionalDependencyError(ImportError):
    """Raised when a component-specific optional dependency is not installed."""

    def __init__(self, component: str, extra: str, package: str) -> None:
        super().__init__(
            f"{component} requires optional dependency {package!r}; install with "
            f"`pip install eventful[{extra}]`."
        )
        self.component = component
        self.extra = extra
        self.package = package


def require_optional(component: str, extra: str, package: str) -> ModuleType:
    """Import an optional package without hiding defects inside Eventful modules."""
    try:
        return import_module(package)
    except ModuleNotFoundError as exc:
        if exc.name == package.split(".", 1)[0]:
            raise OptionalDependencyError(component, extra, package) from exc
        raise
