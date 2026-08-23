# API reference

This page documents the public Eventful 0.2 API whose behavior is exercised by
the project's conformance and extension tests. A **stable** label denotes the
supported local-dispatch facade retained from 0.1. **Provisional** APIs are public
and tested in 0.2, but may change before 1.0. None of the APIs on this page is
experimental or internal.

Signatures below use the public import names. Unless a section says otherwise,
objects are process-local, do not own external resources, have no `close()` method,
and require no optional extra. The [work register](work-register.md) tracks deferred
engineering work; it is not a substitute for the contracts recorded here.

## Local dispatch (stable)

### `Event`

```python
Event(
    type: str,
    payload: Any = None,
    metadata: dict[str, Any] = {},
    tags: set[str] = set(),
)

event.stop_propagation() -> None
event.propagation_stopped -> bool
```

An event carries a hierarchical type, an unconstrained payload, string-keyed
metadata, and filtering tags. The displayed mutable defaults are conceptual:
each instance receives fresh metadata and tag containers. `stop_propagation()`
returns `None` and prevents later listeners in the same dispatch when propagation
control is enabled. Propagation state belongs to the instance, so do not reuse a
stopped event for an unrelated emission.

### `EventBus` and `InMemoryBus`

```python
EventBus(
    config: EventfulConfig | None = None,
    *,
    middleware: Iterable[Middleware] = (),
    schema_registry: SchemaRegistry | None = None,
    observability: Iterable[ObservabilityProvider] = (),
)
InMemoryBus(...)  # identical constructor and behavior
```

`EventBus` implements local registration, routing, and dispatch. `InMemoryBus` is
the explicit default backend name and currently has the same behavior. Neither
class publishes to a broker, persists events, nor owns a closeable resource.

#### Registration and extension mutation

```python
bus.register(
    topic: str,
    listener: Callable[[Event], Any],
    priority: int = 0,
    tags: Iterable[str] = (),
    filter_fn: Callable[[Event], bool] | None = None,
    once: bool = False,
) -> None
bus.unregister(topic: str, listener: Callable[[Event], Any]) -> bool
bus.set_error_handler(handler: ErrorHandler | None) -> None
bus.add_middleware(middleware: Middleware) -> None
bus.remove_middleware(middleware: Middleware) -> bool
bus.set_schema_registry(registry: SchemaRegistry | None) -> None
bus.add_observability_provider(provider: ObservabilityProvider) -> None
bus.remove_observability_provider(provider: ObservabilityProvider) -> bool
```

- `register` raises `ValueError` for an empty topic and `TypeError` for a
  non-callable listener. `*` matches exactly one dot-separated segment and `**`
  matches the remaining suffix.
- Higher priorities run first; equal priorities retain registration order.
  Required tags must be a subset of event tags; `filter_fn(event)` must be truthy.
- Duplicate registrations are independent. `unregister` removes the first match.
  Removal methods return whether an item was present; add/set methods return
  `None`. Provider and registry setters raise `TypeError` for objects that do not
  satisfy their runtime-checkable contracts.
- A `once` registration is removed before its callback runs, including when the
  callback fails or recursively emits the same topic.

Registration and routing snapshots are lock-protected. Application callbacks run
without the registration lock. Changes during dispatch affect the next emission,
not the listener snapshot already in progress.

#### Explicit dispatch

```python
bus.emit_sync(event: Event | dict[str, Any] | Any) -> list[Any]
await bus.emit_async(event: Event | dict[str, Any] | Any) -> list[Any]
```

- Both methods normalize dictionaries and event-like values into `Event` objects
  and return successful callback values in dispatch order.
- `emit_sync` rejects declared async listeners before invoking them. If a regular
  function or middleware dynamically returns an awaitable, Eventful closes it
  when possible and raises `AsyncDispatchRequired`.
- `emit_async` accepts synchronous and asynchronous middleware/listeners and awaits
  awaitable results. Listeners are sequential, never implicitly concurrent.

#### Compatibility dispatch

```python
bus.emit(
    event: Event | dict[str, Any] | Any,
    *,
    async_: bool | None = None,
) -> list[Any] | Awaitable[list[Any]]
```

The compatibility method returns a list for an all-synchronous snapshot and an
awaitable when it detects an `async def` listener or middleware. `async_=False`
and `async_=True` force the corresponding path. Detection cannot predict a regular
function that dynamically returns an awaitable, so explicit dispatch is preferred.

#### Errors and propagation

Listener and middleware exceptions are logged and dispatch continues by default.
`set_error_handler(callback)` makes the callback receive `(exception, event,
listener)`; if it raises, dispatch stops and that exception escapes. Passing `None`
restores logging. Schema validation happens before listener selection and raises
`SchemaValidationError`. Observability failures are logged and isolated.

Calling `event.stop_propagation()` stops later listeners when
`EventfulConfig.propagation_enabled` is true. A listener can equivalently call
the root-exported `stop_propagation()` helper, which raises `StopPropagation` as
a control-flow signal. The stopping listener contributes no result because it
does not return; the signal is not reported to the error handler, failure log,
or failure observability. When `propagation_enabled` is false, both forms of
propagation control are disabled: `Event.stop_propagation()` state is ignored,
and `StopPropagation` is consumed while dispatch continues with later listeners.
Nested emissions are depth-first.
See [core dispatch semantics](core-semantics.md) for the normative behavior table
and [cross-cutting extension points](extensions.md) for ordering details.

### Root facade

```python
get_default_bus() -> EventBus
set_default_bus(bus: EventBus) -> None
emit(event, *, async_: bool | None = None) -> Any
emit_sync(event) -> list[Any]
await emit_async(event) -> list[Any]
```

The root package lazily owns a process-wide default `InMemoryBus`. `set_default_bus`
replaces the reference but does not close the previous bus and provides no
task-local/request-local isolation. Dispatch helper return values and exceptions
are exactly those of the corresponding bus methods.

### `@listener`

```python
@listener(
    topic: str | None = None,
    *,
    priority: int = 0,
    tags: Iterable[str] = (),
    filter: Callable[[Event], bool] | None = None,
    once: bool = False,
)
```

The decorator registers immediately on the process-local default bus, uses the
function name when `topic` is `None`, and returns the original function. It has the
same registration errors as `EventBus.register`. Applications needing explicit
ownership or test isolation should call `bus.register` instead.

## Redis Pub/Sub transport (provisional)

**Optional extra:** `eventful[redis]` (`redis>=5`). Importing the module is safe,
but constructing `RedisTransport` raises `OptionalDependencyError` when
`redis.asyncio` is unavailable. See the [Redis operational guide](redis.md) for its
live, at-most-once delivery model and reconnection boundary.

### `RedisTransport`

```python
RedisTransport(
    url: str,
    *,
    codec: Codec | None = None,
    channel_prefix: str = "eventful:",
    poll_timeout: float = 1.0,
    client: Any | None = None,
    **redis_options: Any,
)

transport.publisher() -> RedisPublisher
transport.consumer(topic: str) -> RedisConsumer
transport.channel(topic: str) -> str
await transport.close() -> None
async with transport as open_transport: ...
```

Construction is lazy with respect to network I/O. It raises `ValueError` for an
empty URL or non-positive poll timeout. Without `client=`, it creates and owns a
redis-py client using `Redis.from_url(url, decode_responses=False,
**redis_options)`; an injected client remains caller-owned. The default codec is
`JsonCodec` and is shared by all endpoints.

`publisher()` repeatedly returns the same publisher. `consumer()` creates a new,
independently owned exact-topic subscription and raises `ValueError` for an empty
topic. `channel()` returns `channel_prefix + topic`. Endpoint creation after close
raises `TransportError`.

`close()` is idempotent: it closes all consumers and the publisher, then closes
only a transport-created client. Consumer/client shutdown failures become
`TransportError`. Async context exit calls `close()`; entry returns the transport
and rejects a previously closed transport.

### `RedisPublisher`

```python
await publisher.publish(event: Event) -> None
await publisher.close() -> None
```

`publish` encodes the full event and publishes bytes to the prefixed exact-type
channel. It returns `None` (not Redis's subscriber count), raises `TypeError` for a
non-`Event`, `TransportError` for an empty type, closed endpoint/transport, or Redis
client failure, and preserves `CodecError` and `asyncio.CancelledError` unchanged.
Client failures are retained as the exception cause.

Publisher close is idempotent and closes only this lightweight endpoint—not the
transport, consumers, or shared client. A closed publisher cannot be reopened.

### `RedisConsumer`

```python
consumer.topic -> str
await consumer.subscribe() -> None
consumer.consume() -> AsyncIterator[Event]
await consumer.close() -> None
```

`topic` is the immutable unprefixed exact topic. `subscribe()` eagerly establishes
one subscription and is idempotent. `consume()` subscribes lazily, allows only one
active iterator, and yields decoded, matching events sequentially. A second active
iterator or use after close raises `TransportError`.

Non-byte payloads, invalid codec documents, and decoded event-type mismatches end
consumption with `TransportError`; terminal Redis errors are translated likewise.
Cancellation remains `asyncio.CancelledError`. Ending, explicitly closing, or
cancelling the iterator permanently closes its consumer and Pub/Sub resource.
`close()` unsubscribes and closes that resource idempotently without closing the
shared Redis client; cleanup failures raise `TransportError`.

## PostgreSQL persistence (provisional)

**Optional extra:** `eventful[postgres]` (`asyncpg>=0.29`). Construction raises
`OptionalDependencyError` when `asyncpg` is unavailable. See the
[PostgreSQL operational guide](postgres.md) for migration privileges, durability,
locking, and replay guidance.

### `PostgresPersistence`

```python
PostgresPersistence(
    dsn: str,
    *,
    table: str = "eventful_events",
    codec: Codec | None = None,
    pool: Any | None = None,
    min_pool_size: int = 1,
    max_pool_size: int = 10,
    command_timeout: float = 60.0,
    read_batch_size: int = 500,
)

await store.open() -> None
await store.migrate() -> None
await store.append(
    event: Event,
    *,
    idempotency_key: str | None = None,
    expected_position: str | None = None,
) -> str
store.read(*, after: str | None = None) -> AsyncIterator[Event]
await store.close() -> None
async with store as open_store: ...
```

Construction performs no connection. It raises `ValueError` for an empty DSN, an
unsafe/over-40-character table identifier, an invalid pool-size range, a
non-positive command timeout, or a read batch size below one. `JsonCodec` is the
default. A supplied pool is caller-owned; otherwise the store lazily creates and
owns an asyncpg pool.

`open()` creates an owned pool once and does **not** migrate. `migrate()` opens as
needed and applies the concurrency-safe, forward-only version-1 schema; both are
idempotent. Pool and migration failures become `StoreError`, while cancellation is
preserved. A database schema newer than supported also raises `StoreError`.

`append()` returns the database position as a decimal string. It raises `TypeError`
for a non-`Event`, `StoreError` for an empty event type, `ValueError` for an empty
idempotency key, and `StoreError` for malformed positions, codec/database failures,
or reuse of an idempotency key for different encoded content. A byte-identical
idempotent retry returns its original position. `expected_position` must equal the
current maximum; `"-1"` means an empty table and mismatch raises
`OptimisticConcurrencyError`.

`read()` yields decoded events in ascending position order, strictly after the
optional non-negative canonical decimal cursor. Invalid cursors, unsupported media
types, corrupt data, event-type mismatches, and database failures raise
`StoreError`. The iterator owns a connection and repeatable-read transaction until
exhausted or closed, and reads a stable snapshot in bounded batches.

`close()` is idempotent, permanently rejects later operations with `StoreError`,
and closes only an owned pool. Async context entry opens but deliberately does not
migrate; exit closes owned resources. Pool-close failures become `StoreError`.

## Framework adapters (provisional)

Adapters never mutate the process-global default bus. See the
[FastAPI and Starlette guide](frameworks.md) for complete application examples and
the ASGI lifespan boundary.

### FastAPI

**Optional extra:** `eventful[fastapi]` (`fastapi>=0.110`, which includes the
Starlette dependency). Importing `eventful.adapters.fastapi` raises
`OptionalDependencyError` if FastAPI or Starlette is unavailable.

```python
event_bus_dependency(
    bus: EventBus | None = None,
    *,
    state_key: str = "eventful_bus",
) -> Callable[[Any], EventBus]

install_eventful(
    app: Any,
    bus: EventBus | None = None,
    **options: Any,
) -> None
```

`event_bus_dependency` returns a FastAPI dependency whose request annotation is
`fastapi.Request`. Each call returns the explicitly captured bus, if supplied;
otherwise it delegates to `request_event_bus(request, state_key=...)` and therefore
raises `RuntimeError` when middleware state is absent. It owns and closes nothing.

`install_eventful` returns `None` and installs `EventfulMiddleware` through the
application's `add_middleware`; `options` are forwarded to that middleware. Bus
ownership and constructor errors are therefore exactly those described below.

### Starlette

**Optional extra:** `eventful[starlette]` (`starlette>=0.37`). Importing this module
raises `OptionalDependencyError` when Starlette is unavailable.

```python
EventfulMiddleware(
    app: Any,
    bus: EventBus | None = None,
    *,
    bus_factory: Callable[[], EventBus] | None = None,
    close_on_shutdown: bool | None = None,
    state_key: str = "eventful_bus",
)

await middleware(scope: dict[str, Any], receive: Any, send: Any) -> None
await middleware.close() -> None

add_eventful_middleware(
    app: Any,
    bus: EventBus | None = None,
    **options: Any,
) -> None

request_event_bus(
    request: Any,
    *,
    state_key: str = "eventful_bus",
    default: EventBus | None = None,
) -> EventBus
```

`EventfulMiddleware` raises `ValueError` when both `bus` and `bus_factory` are
given or when `state_key` is empty. It attaches its one application bus to HTTP and
WebSocket scope state, then returns the wrapped application's result (`None` under
ASGI). An injected bus is caller-owned by default; a factory/default-created bus is
middleware-owned. `close_on_shutdown` explicitly overrides that policy.

On `lifespan.shutdown.complete`, cleanup finishes before the success message is
forwarded. `close()` is idempotent and, only when ownership is enabled, calls a
present `bus.close()` and awaits an awaitable result. Close exceptions propagate.

`add_eventful_middleware` returns `None` and forwards `bus` and all options to the
application middleware installer. `request_event_bus` returns the state bus, then
the explicit `default` when state is absent; without either it raises `RuntimeError`.
Neither helper takes lifecycle ownership independently.

## Codec and store references (provisional)

### `JsonCodec`

```python
JsonCodec()
codec.media_type  # "application/json"
codec.encode(event: Event) -> bytes
codec.decode(data: bytes) -> Event
```

No optional extra is required and no resources are owned. `encode` produces
deterministic UTF-8 JSON for all four public event fields (tags are sorted), returns
new `bytes`, raises `TypeError` for a non-`Event`, and wraps JSON serialization
failures in `CodecError`. `decode` requires `bytes` (`TypeError` otherwise), returns
a distinct `Event`, and raises `CodecError` for invalid UTF-8/JSON, a non-object
document, missing/empty/non-string type, non-object metadata, or non-string tags.

### `InMemoryEventStore`

```python
InMemoryEventStore()
await store.append(event: Event) -> str
store.read(*, after: str | None = None) -> AsyncIterator[Event]
await store.close() -> None
async with store as open_store: ...
```

No optional extra is required. The store owns only its in-memory snapshots.
`append` deep-copies an `Event`, returns its zero-based decimal position, raises
`TypeError` for non-events, and wraps copy failures in `StoreError`. `read` returns
deep copies from a stable snapshot; `after` is exclusive and must be a canonical
non-negative decimal string or `StoreError` is raised. Caller mutations on either
side never mutate stored values.

`close()` is asynchronous and idempotent; it retains data only until garbage
collection but permanently rejects append/read with `StoreError`. Async context
entry returns the open store and exit closes it.

## Listener middleware (provisional)

### `MiddlewareChain`

```python
MiddlewareChain(middleware: tuple[Middleware, ...] = ())
chain.add(middleware: Middleware) -> None
chain.remove(middleware: Middleware) -> bool
chain.snapshot() -> tuple[Middleware, ...]
chain.requires_async() -> bool
chain.invoke_sync(event: Event, handler: EventHandler) -> Any
await chain.invoke_async(event: Event, handler: EventHandler) -> Any
```

The chain owns a thread-safe list, not the middleware callables, and needs no close
or extra. The first item is outermost around every selected listener. `add` rejects
non-callables with `TypeError`, ignores duplicates, and returns `None`; `remove`
returns whether present. `snapshot` is an immutable ordered copy and
`requires_async` reports declared async callables.

`invoke_sync` returns the final value and closes a final awaitable when possible
before raising `AsyncDispatchRequired`. `invoke_async` awaits middleware and handler
results as needed and returns the final value. Other middleware/handler exceptions
propagate to the bus, which applies its listener error policy.

## Schemas (provisional)

```python
class EventSchema(Protocol):
    def validate(self, event: Event) -> None: ...

Schema = EventSchema | Callable[[Event], bool | None]

InMemorySchemaRegistry()
registry.register(event_type: str, schema: object) -> None
registry.unregister(event_type: str) -> bool
registry.resolve(event_type: str) -> Schema | None
registry.validate(event: Event) -> None
```

`EventSchema` is runtime-checkable. The in-memory registry owns exact-type
associations only, not validator lifecycles, and needs no extra or close.
`register` replaces an existing association, raises `ValueError` for an empty type
and `TypeError` unless the schema is callable or implements `EventSchema`.
`unregister` reports whether present; `resolve` returns the validator or `None`.

`validate` returns `None` for an unknown or valid event. A callable rejects by
returning exactly `False`; protocol objects reject by raising. Existing
`SchemaValidationError` passes through, while every other validation exception is
wrapped in `SchemaValidationError` with the original cause.

## Observability (provisional)

```python
Observation(event_type: str, attributes: MappingProxyType[str, Any])

InMemoryObservabilityProvider()
provider.record_event(event: Event, attributes: Mapping[str, Any]) -> None
provider.records -> tuple[Observation, ...]
provider.clear() -> None
```

`Observation` is a frozen dataclass. The provider owns an in-memory, thread-safe
buffer and needs no extra or close. `record_event` deep-copies attributes into an
immutable mapping, stores only the event type (not payload or the event object),
and returns `None`; copy errors propagate. `records` returns a stable tuple snapshot
and `clear` empties the buffer. When installed on a bus, provider failures are
logged and cannot alter dispatch results. Dispatch emits started/completed signals
and failure signals described in the [extension guide](extensions.md#observability).

## Configuration (provisional sources; stable `EventfulConfig`)

### `EventfulConfig`

```python
EventfulConfig(
    enable_priorities: bool = True,
    propagation_enabled: bool = True,
    redis_url: str = "redis://localhost:6379",
    redis_channel: str = "eventful",
    redis_reconnect_backoff: float = 1.0,
    file_path: str = "events.log",
    file_max_size: int = 10485760,
    file_backup_count: int = 5,
    postgres_url: str = "postgresql://localhost:5432/eventful",
    postgres_table: str = "events",
    logging_enabled: bool = True,
    logging_level: str = "INFO",
    max_queue_size: int = 10000,
    extra: dict[str, Any] = {},
)

EventfulConfig.from_env() -> EventfulConfig
EventfulConfig.from_mapping(
    values: Mapping[str, Any], *, allow_extra: bool = True
) -> EventfulConfig
get_config() -> EventfulConfig
set_config(config: EventfulConfig) -> None
```

No extra or close is required. `from_env` reads matching `EVENTFUL_<FIELD>` names.
`from_mapping` does not mutate input; it converts string booleans, integers, and
floats, returns a new config, and raises `ConfigurationError` for invalid scalar
text or a non-mapping `extra`. Unknown keys enter `config.extra`, or raise
`ConfigurationError` when `allow_extra=False`. `get_config` lazily returns the
process-global config; `set_config` replaces it and returns `None` without closing
or validating ownership.

### Configuration sources

```python
MappingSource(values: Mapping[str, Any])
source.load() -> Mapping[str, Any]

EnvironmentSource(prefix: str = "EVENTFUL_")
source.load() -> Mapping[str, Any]

CompositeSource(sources: Sequence[object])
source.load() -> Mapping[str, Any]
```

Sources need no optional extra or close and return immutable mapping snapshots.
`MappingSource` defensively copies its constructor input. `EnvironmentSource`
raises `ValueError` for an empty prefix, selects matching variables, removes the
prefix, lowercases keys, and leaves values as strings. `CompositeSource` raises
`ValueError` for no sources and `TypeError` if any lacks callable `load()`; it
captures the ordered sequence and merges left-to-right, so later sources win.
Exceptions raised by constituent `load()` calls propagate.

## Plugins (provisional)

```python
PluginManager()
manager.register(plugin: Plugin) -> None
manager.get(name: str) -> Plugin
manager.plugins -> tuple[Plugin, ...]
manager.configure(settings: Mapping[str, Mapping[str, Any]]) -> None
manager.discover(group: str = "eventful.plugins") -> tuple[Plugin, ...]
```

No optional extra is required. The manager owns registrations, not plugin
resources; it has no close hook. A plugin must expose non-empty `name: str` and
`configure(settings: Mapping[str, Any]) -> None`. `register` raises `TypeError` for
a structurally invalid plugin and `ContractError` for an empty or duplicate name.
`get` returns the registered object or raises `KeyError`; `plugins` returns a tuple
in registration order.

`configure` rejects settings for unknown names with `ContractError`, otherwise
calls every registered plugin in order with a fresh dictionary (empty when omitted)
and returns `None`; plugin exceptions propagate. `discover` explicitly loads the
requested Python entry-point group, instantiates loaded classes, registers each
object under the same rules, and returns newly discovered plugins as a tuple.
Loading executes third-party code, and load/constructor/registration exceptions
propagate. See the [plugin operational notes](extensions.md#plugins).

## Runtime contracts (provisional)

The `eventful.contracts` protocols—`AsyncCloseable`, `Publisher`, `Subscription`,
`Consumer`, `Transport`, `EventBusContract`, `RouterContract`,
`DispatcherContract`, `Middleware`, `Codec`, `EventStore`, `Plugin`,
`ConfigurationSource`, `SchemaRegistry`, and `ObservabilityProvider`—are public,
`@runtime_checkable` structural interfaces. `EventHandler` is
`Callable[[Event], Any]`.

Protocol methods have the signatures shown by their concrete APIs above, except
that the portable `EventStore.append(event)` contract has no PostgreSQL-specific
keywords. `isinstance(value, ProtocolName)` checks only structural presence, not
behavior or signatures, returns `bool`, owns nothing, and raises the standard
`TypeError` if used with an unsubscripted/non-runtime protocol operation unsupported
by Python. Behavioral guarantees come from the reference implementations and
conformance tests described on this page; see [contracts](contracts.md) for guidance
on implementing third-party components.
