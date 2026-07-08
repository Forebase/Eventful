"""
Tests for event model.
"""

import pytest
from eventful.event import Event, ensure_event


class TestEvent:
    def test_event_creation(self):
        event = Event(type="test.event", payload="data", tags={"tag1", "tag2"})
        assert event.type == "test.event"
        assert event.payload == "data"
        assert event.tags == {"tag1", "tag2"}
        assert not event.propagation_stopped

    def test_event_stop_propagation(self):
        event = Event(type="test.event")
        event.stop_propagation()
        assert event.propagation_stopped

    def test_ensure_event_from_dict(self):
        data = {"type": "test.event", "payload": "data", "tags": ["tag1"]}
        event = ensure_event(data)
        assert isinstance(event, Event)
        assert event.type == "test.event"
        assert event.payload == "data"
        assert event.tags == {"tag1"}

    def test_ensure_event_from_object(self):
        class CustomEvent:
            type = "custom.event"
            payload = "custom data"
            tags = ["tag1", "tag2"]

        event = ensure_event(CustomEvent())
        assert isinstance(event, Event)
        assert event.type == "custom.event"
        assert event.payload == "custom data"
        assert event.tags == {"tag1", "tag2"}

    def test_ensure_event_from_primitive(self):
        event = ensure_event("simple string")
        assert isinstance(event, Event)
        assert event.type == "str"
        assert event.payload == "simple string"
