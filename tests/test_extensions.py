"""Behavior tests for cross-cutting extension reference implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from eventful import Event, EventBus
from eventful.config import EventfulConfig
from eventful.configuration import CompositeSource, EnvironmentSource, MappingSource
from eventful.contracts import (
    ConfigurationSource,
    ObservabilityProvider,
    Plugin,
    SchemaRegistry,
)
from eventful.exceptions import ConfigurationError, ContractError, SchemaValidationError
from eventful.observability import InMemoryObservabilityProvider
from eventful.plugins import PluginManager
from eventful.schemas import InMemorySchemaRegistry


class SamplePlugin:
    """Record settings applied through the plugin manager."""

    name = "sample"

    def __init__(self) -> None:
        """Create an unconfigured sample plugin."""
        self.settings: Mapping[str, Any] | None = None

    def configure(self, settings: Mapping[str, Any]) -> None:
        """Retain a defensive settings snapshot."""
        self.settings = dict(settings)


def test_middleware_wraps_listeners_in_outermost_first_order() -> None:
    """Apply middleware around every selected listener deterministically."""
    calls: list[str] = []

    def outer(event, next_handler):
        calls.append("outer.before")
        result = next_handler(event)
        calls.append("outer.after")
        return result

    def inner(event, next_handler):
        calls.append("inner.before")
        result = next_handler(event)
        calls.append("inner.after")
        return result

    bus = EventBus(middleware=(outer, inner))
    bus.register("sample", lambda event: calls.append("listener") or "result")

    assert bus.emit_sync(Event("sample")) == ["result"]
    assert calls == [
        "outer.before",
        "inner.before",
        "listener",
        "inner.after",
        "outer.after",
    ]


@pytest.mark.asyncio
async def test_async_middleware_is_detected_and_awaited() -> None:
    """Select compatibility async dispatch when middleware is declared async."""

    async def middleware(event, next_handler):
        return f"wrapped:{await next_handler(event)}"

    async def listener(event):
        return event.payload

    bus = EventBus(middleware=(middleware,))
    bus.register("sample", listener)

    assert await bus.emit(Event("sample", "value")) == ["wrapped:value"]

    sync_bus = EventBus(middleware=(middleware,))
    sync_bus.register("sample", lambda event: event.payload)
    assert await sync_bus.emit(Event("sample", "sync")) == ["wrapped:sync"]


def test_schema_validation_precedes_listener_selection() -> None:
    """Prevent invalid events from reaching filters or listeners."""
    registry = InMemorySchemaRegistry()
    registry.register(
        "user.created",
        lambda event: isinstance(event.payload, dict) and "id" in event.payload,
    )
    calls: list[Event] = []
    bus = EventBus(schema_registry=registry)
    bus.register("user.created", calls.append)

    with pytest.raises(SchemaValidationError, match="user.created"):
        bus.emit_sync(Event("user.created", {}))

    assert calls == []
    valid = Event("user.created", {"id": 7})
    assert bus.emit_sync(valid) == [None]
    assert calls == [valid]


def test_observability_signals_are_isolated_from_dispatch(caplog) -> None:
    """Record lifecycle signals while ignoring provider defects."""
    provider = InMemoryObservabilityProvider()

    class BrokenProvider:
        def record_event(self, event, attributes):
            raise RuntimeError("telemetry unavailable")

    bus = EventBus(observability=(provider, BrokenProvider()))
    bus.register("sample", lambda event: "ok")

    assert bus.emit_sync(Event("sample")) == ["ok"]
    assert [record.attributes["stage"] for record in provider.records] == [
        "dispatch.started",
        "dispatch.completed",
    ]
    assert "Observability provider" in caplog.text


def test_configuration_sources_are_immutable_and_precedence_is_explicit(
    monkeypatch,
) -> None:
    """Merge source snapshots and convert them into typed EventfulConfig values."""
    monkeypatch.setenv("APP_ENABLE_PRIORITIES", "false")
    base = {"enable_priorities": "true", "max_queue_size": "20"}
    source = CompositeSource((MappingSource(base), EnvironmentSource("APP_")))
    base["max_queue_size"] = "999"

    loaded = source.load()
    config = EventfulConfig.from_mapping(loaded)

    assert isinstance(source, ConfigurationSource)
    assert config.enable_priorities is False
    assert config.max_queue_size == 20
    with pytest.raises(TypeError):
        loaded["new"] = "value"  # type: ignore[index]
    with pytest.raises(ConfigurationError, match="unknown"):
        EventfulConfig.from_mapping({"unknown": 1}, allow_extra=False)


def test_plugin_manager_registration_configuration_and_discovery(monkeypatch) -> None:
    """Enforce unique names and explicit third-party discovery."""
    plugin = SamplePlugin()
    manager = PluginManager()
    manager.register(plugin)

    assert isinstance(plugin, Plugin)
    manager.configure({"sample": {"enabled": True}})
    assert plugin.settings == {"enabled": True}
    with pytest.raises(ContractError, match="already"):
        manager.register(SamplePlugin())
    with pytest.raises(ContractError, match="unknown"):
        manager.configure({"missing": {}})

    class EntryPoint:
        def load(self):
            return type("Discovered", (SamplePlugin,), {"name": "discovered"})

    monkeypatch.setattr(
        "eventful.plugins.entry_points", lambda **kwargs: (EntryPoint(),)
    )
    assert [item.name for item in manager.discover()] == ["discovered"]


def test_reference_extensions_satisfy_runtime_contracts() -> None:
    """Keep reference extension implementations structurally discoverable."""
    assert isinstance(InMemorySchemaRegistry(), SchemaRegistry)
    assert isinstance(InMemoryObservabilityProvider(), ObservabilityProvider)
