"""
Tests for event bus.
"""

import pytest
import asyncio
from eventful.bus import EventBus, InMemoryBus
from eventful.event import Event


class TestEventBus:
    def test_register_listener(self):
        bus = EventBus()

        def test_listener(event):
            return "processed"

        bus.register("test.event", test_listener)
        results = bus.emit(Event(type="test.event"))
        assert results == ["processed"]

    def test_priority_ordering(self):
        bus = EventBus()
        calls = []

        def high_priority(event):
            calls.append("high")

        def low_priority(event):
            calls.append("low")

        bus.register("test.event", low_priority, priority=0)
        bus.register("test.event", high_priority, priority=1)
        bus.emit(Event(type="test.event"))
        assert calls == ["high", "low"]

    def test_once_listener(self):
        bus = EventBus()
        calls = []

        def one_time_listener(event):
            calls.append("called")

        bus.register("test.event", one_time_listener, once=True)
        bus.emit(Event(type="test.event"))
        bus.emit(Event(type="test.event"))
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_async_listener(self):
        bus = EventBus()

        async def async_listener(event):
            return "async result"

        bus.register("test.event", async_listener)
        results = await bus.emit(Event(type="test.event"))
        assert results == ["async result"]

    def test_propagation_stop(self):
        bus = EventBus()
        calls = []

        def stopping_listener(event):
            calls.append("stop")
            event.stop_propagation()

        def never_called_listener(event):
            calls.append("never")

        bus.register("test.event", stopping_listener)
        bus.register("test.event", never_called_listener)
        bus.emit(Event(type="test.event"))
        assert calls == ["stop"]


class TestInMemoryBus:
    def test_queue_behavior(self):
        bus = InMemoryBus()
        calls = []

        def listener1(event):
            calls.append("l1")
            bus.emit(Event(type="nested.event"))

        def listener2(event):
            calls.append("l2")

        bus.register("test.event", listener1)
        bus.register("nested.event", listener2)
        bus.emit(Event(type="test.event"))
        assert calls == ["l1", "l2"]
