from __future__ import annotations
from eventful import Event, InMemoryBus


def test_readme_quickstart_pattern() -> None:
    bus = InMemoryBus()
    def handle(event: Event) -> str:
        return f"hello {event.payload}"
    bus.register("user.created", handle)
    assert bus.emit(Event(type="user.created", payload="Ada")) == ["hello Ada"]
