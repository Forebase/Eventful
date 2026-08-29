# Eventful

Eventful 0.3.0 is a typed event toolkit for Python 3.13 and 3.14. Its supported core is the local dispatcher (`Event`, `EventBus`, `InMemoryBus`, `listener`, `emit_sync`, `emit_async`, and the compatibility helper `emit`), with tested Redis, PostgreSQL, file-persistence, FastAPI, and Starlette integrations.

## Install

```bash
pip install eventful
```

Optional integrations are component-specific and provisional:

```bash
pip install 'eventful[redis]'
pip install 'eventful[postgres]'
pip install 'eventful[file]'  # explicit but dependency-free
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
assert bus.emit_sync(Event(type="user.created", payload="Ada")) == ["hello Ada"]
```

## API status

No API is frozen before 1.0. The root facade remains backward compatible within the documented deprecation policy. Production use must be limited to the guarantees and deployment models in [`docs/production-readiness.md`](docs/production-readiness.md).

See `docs/index.md` for the documentation map and `docs/work-register.md` for deferred work.

The provisional `JsonCodec` and `InMemoryEventStore` are dependency-free
conformance references, not production transport or durable-storage integrations.
`RedisTransport` provides documented live, at-most-once Pub/Sub delivery; it does
not provide replay or durability.
`PostgresPersistence` provides transactional append/replay with explicit migrations,
idempotency keys, and optional table-wide optimistic concurrency.
`FilePersistence` is a deterministic, single-process UTF-8 JSON Lines backend with
bounded rotation and physical-line replay offsets; it has no third-party dependency.
FastAPI and Starlette adapters expose application-owned buses through request state
and coordinate opt-in ASGI lifespan cleanup. Middleware, schemas, observability,
configuration sources, and plugins have dependency-free provisional references.

## Async utility lifecycle

`eventful.utilities.async_debounce(interval)` is a synchronous decorator factory
for async callbacks. Calling its async wrapper schedules the latest invocation and
coalesces earlier pending invocations. Applications should `await wrapper.flush()`
to deliver pending work immediately or `await wrapper.cancel()` to discard it;
both methods wait for associated tasks, so either can be used during event-loop
shutdown. Background callback failures are observed internally and re-raised by
the next wrapper, `flush`, or `cancel` call rather than being reported as
unretrieved task exceptions. A callback run directly by `flush` raises through
that `flush` call.
