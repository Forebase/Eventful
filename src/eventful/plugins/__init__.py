"""Provisional explicit plugin registration and entry-point discovery.

Plugin loading executes third-party Python code and therefore occurs only when an
application calls `discover`. Registration, configuration, and duplicate-name
policy are otherwise dependency-free and deterministic.
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import entry_points
from threading import RLock
from typing import Any

from eventful.api_status import ApiStatus
from eventful.contracts import Plugin
from eventful.exceptions import ContractError


class PluginManager:
    """Own uniquely named plugins and apply namespaced settings."""

    def __init__(self) -> None:
        """Create an empty thread-safe manager."""
        self._plugins: dict[str, Plugin] = {}
        self._lock = RLock()

    def register(self, plugin: Plugin) -> None:
        """Register a structurally valid plugin under its stable unique name."""
        if not isinstance(plugin, Plugin):
            raise TypeError("plugin must implement the Plugin contract")
        if not plugin.name:
            raise ContractError("plugin name must not be empty")
        with self._lock:
            if plugin.name in self._plugins:
                raise ContractError(f"plugin already registered: {plugin.name!r}")
            self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Plugin:
        """Return a registered plugin or raise a descriptive key error."""
        with self._lock:
            try:
                return self._plugins[name]
            except KeyError as exc:
                raise KeyError(f"plugin is not registered: {name!r}") from exc

    @property
    def plugins(self) -> tuple[Plugin, ...]:
        """Return plugins in deterministic registration order."""
        with self._lock:
            return tuple(self._plugins.values())

    def configure(self, settings: Mapping[str, Mapping[str, Any]]) -> None:
        """Configure registered plugins from mappings keyed by plugin name."""
        unknown = set(settings).difference(plugin.name for plugin in self.plugins)
        if unknown:
            raise ContractError(
                f"settings provided for unknown plugins: {sorted(unknown)!r}"
            )
        for plugin in self.plugins:
            plugin.configure(dict(settings.get(plugin.name, {})))

    def discover(self, group: str = "eventful.plugins") -> tuple[Plugin, ...]:
        """Load and register plugin objects from an explicit entry-point group."""
        discovered: list[Plugin] = []
        for entry_point in entry_points(group=group):
            loaded = entry_point.load()
            plugin = loaded() if isinstance(loaded, type) else loaded
            self.register(plugin)
            discovered.append(plugin)
        return tuple(discovered)


API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "PluginManager"]
