# API reference

Eventful's supported 0.2 surface is an in-process event dispatcher. Transport,
persistence, adapter, and extension namespaces are provisional or experimental;
their boundaries are described in the [work register](work-register.md).

## `Event`

```python
Event(
    type: str,
    payload: Any = None,
    metadata: dict[str, Any] = {},
    tags: set[str] = set(),
)
```

An event carries a hierarchical type, an unconstrained payload, string-keyed
metadata, and filtering tags. `stop_propagation()` prevents later listeners in the
same dispatch when propagation control is enabled. Propagation state belongs to the
instance, so do not reuse a stopped event for an unrelated emission.

## `EventBus` and `InMemoryBus`

`EventBus` implements local registration, routing, and dispatch. `InMemoryBus` is
the explicit default backend name and currently has the same behavior. Neither
class publishes to a broker or persists events.

The constructor also accepts ordered `middleware`, an optional `schema_registry`,
and best-effort `observability` providers. These components can be changed for later
dispatches through `add_middleware`, `remove_middleware`, `set_schema_registry`,
`add_observability_provider`, and `remove_observability_provider`. See
[cross-cutting extension points](extensions.md) for ordering and failure boundaries.

### Registration

```python
bus.register(
    topic,
    listener,
    priority=0,
    tags=(),
    filter_fn=None,
    once=False,
)
bus.unregister(topic, listener) -> bool
```

- `*` matches exactly one dot-separated topic segment.
- `**` matches the remaining topic suffix.
- Higher priorities run first; equal priorities retain registration order.
- Required tags must be a subset of the event tags.
- `filter_fn(event)` must return truthy for the listener to match.
- Duplicate registrations are independent. `unregister` removes the first match.
- A `once` registration is removed before its callback runs, including when the
  callback fails or recursively emits the same topic.

Registration and routing snapshots are lock-protected. Application callbacks run
without the registration lock. Changes made during dispatch therefore affect the
next emission, not the listener snapshot already in progress.

### Explicit dispatch

```python
bus.emit_sync(event) -> list[Any]
await bus.emit_async(event) -> list[Any]
```

Use these methods in new code:

- `emit_sync` rejects declared async listeners before invoking them. If a regular
  function dynamically returns an awaitable, Eventful closes it when possible and
  raises `AsyncDispatchRequired` instead of leaking a coroutine.
- `emit_async` accepts synchronous and asynchronous listeners and awaits any
  awaitable result.
- Listeners are awaited sequentially; Eventful does not run callbacks concurrently.
- Results contain successful callback return values in dispatch order.

### Compatibility dispatch

```python
bus.emit(event, async_=None)
```

The provisional compatibility method returns a list for an all-synchronous
listener snapshot and an awaitable when it detects a listener declared with
`async def`. `async_=False` and `async_=True` force the corresponding path.
Automatic detection cannot predict a regular function that dynamically returns an
awaitable, so explicit dispatch is recommended.

### Errors and propagation

Listener exceptions are logged and dispatch continues by default. Set an error
handler with `set_error_handler(callback)` to observe failures. If that callback
raises, dispatch stops and its exception escapes. Pass `None` to restore logging.

Calling `event.stop_propagation()` stops later listeners when
`EventfulConfig.propagation_enabled` is true. When false, dispatch continues.

Nested emissions are depth-first: a nested call completes before the next outer
listener begins. Listener registration mutations still follow snapshot semantics.

See [core dispatch semantics](core-semantics.md) for the normative behavior table.

## Root facade

The root package provides a process-local default `InMemoryBus`:

```python
from eventful import emit, emit_async, emit_sync, get_default_bus, set_default_bus
```

`emit_sync` and `emit_async` are explicit helpers. `emit` preserves provisional
automatic detection for compatibility. `set_default_bus` replaces the process-wide
default; it does not provide task-local or request-local isolation.

## `@listener`

```python
@listener("order.created", priority=10, tags={"important"}, once=True)
def handle(event: Event) -> None:
    ...
```

The decorator registers immediately on the process-local default bus and returns
the original function. Applications needing explicit ownership or test isolation
should call `bus.register` instead.
