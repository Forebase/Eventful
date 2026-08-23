"""
Tests for event bus.
"""

import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from eventful import stop_propagation
from eventful.bus import EventBus, InMemoryBus
from eventful.config import EventfulConfig
from eventful.event import Event
from eventful.exceptions import AsyncDispatchRequired


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

    def test_emit_sync_rejects_async_listener_before_invocation(self):
        bus = EventBus()
        calls = []

        async def async_listener(event):
            calls.append(event)

        bus.register("test.event", async_listener)

        with pytest.raises(AsyncDispatchRequired, match="emit_async"):
            bus.emit_sync(Event(type="test.event"))

        assert calls == []

    def test_emit_sync_closes_dynamically_returned_coroutine(self):
        bus = EventBus()

        async def result():
            return "async result"

        def coroutine_factory(event):
            return result()

        bus.register("test.event", coroutine_factory)

        with pytest.raises(AsyncDispatchRequired, match="emit_async"):
            bus.emit_sync(Event(type="test.event"))

    @pytest.mark.asyncio
    async def test_emit_async_awaits_dynamic_awaitable(self):
        bus = EventBus()

        async def result():
            return "async result"

        bus.register("test.event", lambda event: result())

        assert await bus.emit_async(Event(type="test.event")) == ["async result"]

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

    def test_propagation_can_be_disabled(self):
        bus = EventBus(EventfulConfig(propagation_enabled=False))
        calls = []

        def stopping_listener(event):
            calls.append("stop")
            event.stop_propagation()

        bus.register("test.event", stopping_listener)
        bus.register("test.event", lambda event: calls.append("continued"))

        bus.emit_sync(Event(type="test.event"))

        assert calls == ["stop", "continued"]

    def test_stop_propagation_helper_stops_without_listener_failure(self, caplog):
        bus = EventBus()
        calls = []

        def stopping_listener(event):
            calls.append("stop")
            stop_propagation()

        bus.register("test.event", stopping_listener)
        bus.register("test.event", lambda event: calls.append("continued"))

        results = bus.emit_sync(Event(type="test.event"))

        assert calls == ["stop"]
        assert results == []
        assert "Error in listener" not in caplog.text

    @pytest.mark.asyncio
    async def test_async_stop_propagation_helper_stops_without_listener_failure(
        self, caplog
    ):
        bus = EventBus()
        calls = []

        async def stopping_listener(event):
            calls.append("stop")
            stop_propagation()

        bus.register("test.event", stopping_listener)
        bus.register("test.event", lambda event: calls.append("continued"))

        results = await bus.emit_async(Event(type="test.event"))

        assert calls == ["stop"]
        assert results == []
        assert "Error in listener" not in caplog.text

    def test_stop_propagation_helper_is_ignored_when_propagation_is_disabled(self):
        bus = EventBus(EventfulConfig(propagation_enabled=False))
        calls = []

        bus.register("test.event", lambda event: stop_propagation())
        bus.register("test.event", lambda event: calls.append("continued"))

        assert bus.emit_sync(Event(type="test.event")) == [None]
        assert calls == ["continued"]

    def test_listener_failures_log_and_dispatch_continues(self, caplog):
        bus = EventBus()
        bus.register("test.event", lambda event: 1 / 0)
        bus.register("test.event", lambda event: "successful")

        results = bus.emit_sync(Event(type="test.event"))

        assert results == ["successful"]
        assert "Error in listener" in caplog.text

    def test_custom_error_handler_can_stop_dispatch(self):
        bus = EventBus()
        bus.register("test.event", lambda event: 1 / 0)
        bus.set_error_handler(lambda exc, event, listener: (_ for _ in ()).throw(exc))

        with pytest.raises(ZeroDivisionError):
            bus.emit_sync(Event(type="test.event"))

    def test_once_listener_is_removed_even_when_it_fails(self):
        bus = EventBus()
        calls = []

        def failing_listener(event):
            calls.append(event)
            raise RuntimeError("failure")

        bus.register("test.event", failing_listener, once=True)
        bus.emit_sync(Event(type="test.event"))
        bus.emit_sync(Event(type="test.event"))

        assert len(calls) == 1

    def test_once_listener_is_claimed_once_across_concurrent_snapshots(self):
        bus = EventBus()
        snapshot_barrier = Barrier(2)
        calls = 0
        calls_lock = Lock()
        original_snapshot = bus._listener_snapshot

        def listener(event):
            nonlocal calls
            with calls_lock:
                calls += 1

        def synchronized_snapshot(event):
            listeners = original_snapshot(event)
            snapshot_barrier.wait()
            return listeners

        bus.register("test.event", listener, once=True)
        bus._listener_snapshot = synchronized_snapshot  # type: ignore[method-assign]

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(bus.emit_sync, Event(type="test.event"))
                for _ in range(2)
            ]
            for future in futures:
                future.result()

        assert calls == 1

    def test_registration_changes_apply_to_next_snapshot(self):
        bus = EventBus()
        calls = []

        def first(event):
            calls.append("first")
            bus.unregister("test.event", second)

        def second(event):
            calls.append("second")

        bus.register("test.event", first)
        bus.register("test.event", second)

        bus.emit_sync(Event(type="test.event"))
        bus.emit_sync(Event(type="test.event"))

        assert calls == ["first", "second", "first"]

    def test_registration_validates_inputs(self):
        bus = EventBus()

        with pytest.raises(ValueError, match="topic"):
            bus.register("", lambda event: None)
        with pytest.raises(TypeError, match="callable"):
            bus.register("test.event", None)  # type: ignore[arg-type]


class TestInMemoryBus:
    def test_nested_emissions_are_depth_first(self):
        bus = InMemoryBus()
        calls = []

        def listener1(event):
            calls.append("outer-1-start")
            bus.emit_sync(Event(type="nested.event"))
            calls.append("outer-1-end")

        def listener2(event):
            calls.append("nested")

        bus.register("test.event", listener1)
        bus.register("nested.event", listener2)
        bus.register("test.event", lambda event: calls.append("outer-2"))

        bus.emit_sync(Event(type="test.event"))

        assert calls == ["outer-1-start", "nested", "outer-1-end", "outer-2"]
