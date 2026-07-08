"""
Plugin system for eventful.
"""

from .plugin import Plugin, TransportPlugin, PersistencePlugin
from .registry import PluginRegistry, get_plugin_registry, register_plugin

__all__ = [
    "Plugin",
    "TransportPlugin",
    "PersistencePlugin",
    "PluginRegistry",
    "get_plugin_registry",
    "register_plugin",
]
