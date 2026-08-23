# Quick start

## Installation

```bash
pip install eventful
```

## An explicitly owned bus

Prefer an application-owned bus so tests and application instances do not share
registrations:

```python
from eventful import Event, InMemoryBus

bus = InMemoryBus()


def handle_user_created(event: Event) -> str:
    return f"created {event.payload}"


bus.register("user.created", handle_user_created)
assert bus.emit_sync(Event(type="user.created", payload="Alice")) == [
    "created Alice"
]
```

## Async dispatch

Use `emit_async` when any listener may return an awaitable:

```python
import asyncio

from eventful import Event, InMemoryBus

bus = InMemoryBus()


async def send_confirmation(event: Event) -> str:
    await asyncio.sleep(0.01)
    return f"sent to {event.payload}"


bus.register("email.requested", send_confirmation)


async def main() -> None:
    results = await bus.emit_async(
        Event(type="email.requested", payload="user@example.com")
    )
    assert results == ["sent to user@example.com"]


asyncio.run(main())
```

## Root compatibility facade

`listener` and `emit` use a process-local default bus and remain available for
small scripts and 0.1-compatible code:

```python
from eventful import Event, emit_sync, listener


@listener("system.alert", tags={"critical"})
def critical_alert(event: Event) -> str:
    return str(event.payload)


assert emit_sync(
    Event(type="system.alert", payload="Server down", tags={"critical"})
) == ["Server down"]
```

For ordering, errors, propagation, nested emissions, and thread boundaries, read
the [core dispatch semantics](core-semantics.md).
