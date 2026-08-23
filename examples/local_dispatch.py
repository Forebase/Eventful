"""Local dispatch example.

Prerequisite: ``pip install -e .``
Run: ``python examples/local_dispatch.py``
"""

from eventful import Event, InMemoryBus


def main() -> list[object]:
    """Dispatch an event locally and return the listener results."""
    bus = InMemoryBus()

    def handle_user_created(event: Event) -> str:
        return f"created {event.payload}"

    bus.register("user.created", handle_user_created)
    results = bus.emit_sync(Event(type="user.created", payload="Alice"))
    print(results[0])
    return results


if __name__ == "__main__":
    assert main() == ["created Alice"]
