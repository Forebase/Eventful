# Eventful

Eventful 0.2.0 is a pre-alpha foundation for a Python event toolkit. The implemented public facade is a local in-memory dispatcher (`Event`, `EventBus`, `InMemoryBus`, `listener`, and `emit`). v1-oriented packages provide provisional contracts for brokers, durable streams, codecs, stores, middleware, plugins, configuration, schemas, and observability.

## Install

```bash
pip install eventful
```

Optional integrations are component-specific and experimental:

```bash
pip install 'eventful[redis]'
pip install 'eventful[postgres]'
pip install 'eventful[fastapi]'
pip install 'eventful[all]'
```

## Quick start

```python
from eventful import Event, InMemoryBus

bus = InMemoryBus()


def handle(event: Event) -> str:
    return f"hello {event.payload}"

bus.register("user.created", handle)
assert bus.emit(Event(type="user.created", payload="Ada")) == ["hello Ada"]
```

## API status

No API is stable before 1.0. The root facade is preserved for 0.1 compatibility and treated as provisional. Experimental packages are importable for architecture work but should not be treated as production integrations.

See `docs/index.md` for the documentation map and `docs/work-register.md` for deferred work.
