"""
Tests for event router.
"""

import pytest
from eventful.router import Router
from eventful.event import Event
from eventful.listener import Listener, ListenerConfig


class TestRouter:
    def test_exact_match(self):
        router = Router()
        listener = Listener(lambda e: None, ListenerConfig())

        router.add_listener("service.user.created", listener)
        event = Event(type="service.user.created")
        matches = router.get_listeners(event)

        assert len(matches) == 1
        assert matches[0] == listener

    def test_wildcard_single_level(self):
        router = Router()
        listener = Listener(lambda e: None, ListenerConfig())

        router.add_listener("service.user.*", listener)
        event = Event(type="service.user.created")
        matches = router.get_listeners(event)

        assert len(matches) == 1

    def test_wildcard_multi_level(self):
        router = Router()
        listener = Listener(lambda e: None, ListenerConfig())

        router.add_listener("service.**", listener)
        event = Event(type="service.user.created.verified")
        matches = router.get_listeners(event)

        assert len(matches) == 1

    def test_tag_filtering(self):
        router = Router()
        listener = Listener(lambda e: None, ListenerConfig(tags={"important"}))

        router.add_listener("test.event", listener)

        # Event without required tag
        event1 = Event(type="test.event", tags=set())
        matches1 = router.get_listeners(event1)
        assert len(matches1) == 0

        # Event with required tag
        event2 = Event(type="test.event", tags={"important"})
        matches2 = router.get_listeners(event2)
        assert len(matches2) == 1

    def test_custom_filter(self):
        def custom_filter(event):
            return event.payload == "allowed"

        router = Router()
        listener = Listener(lambda e: None, ListenerConfig(filter_fn=custom_filter))

        router.add_listener("test.event", listener)

        # Event that doesn't pass filter
        event1 = Event(type="test.event", payload="blocked")
        matches1 = router.get_listeners(event1)
        assert len(matches1) == 0

        # Event that passes filter
        event2 = Event(type="test.event", payload="allowed")
        matches2 = router.get_listeners(event2)
        assert len(matches2) == 1
