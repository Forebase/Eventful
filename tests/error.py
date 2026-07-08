"""
Tests for error handling.
"""

import pytest
from eventful.error import ErrorHandler
from eventful.event import Event


class TestErrorHandler:
    def test_custom_error_handler(self):
        handler = ErrorHandler()
        calls = []

        def custom_handler(exc, event, listener):
            calls.append((exc, event.type))

        handler.set_handler(custom_handler)

        test_event = Event(type="test.event")
        test_listener = lambda e: None

        handler.handle_error(ValueError("test error"), test_event, test_listener)

        assert len(calls) == 1
        assert calls[0][1] == "test.event"

    def test_default_error_handling(self, caplog):
        handler = ErrorHandler()
        test_event = Event(type="test.event")
        test_listener = lambda e: None

        handler.handle_error(ValueError("test error"), test_event, test_listener)

        assert "Error in listener" in caplog.text
