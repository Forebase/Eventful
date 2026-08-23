# Architectural contracts

The protocols in `eventful.contracts` are provisional capability boundaries. They
contain no optional imports and may be checked with `isinstance`, but runtime
protocol checks verify attribute presence—not signatures or behavior. Eventful
therefore combines static assignments and reusable behavioral conformance tests.

## Design decisions

### Local work is explicit

`EventBusContract` is independent from `Publisher`. A local event bus dispatches
callbacks in the current process and exposes `emit_sync` and `emit_async`. It does
not imply broker delivery. `EventBus`, its router, and its dispatcher are the
current reference implementations.

### I/O boundaries are asynchronous

`Publisher`, `Consumer`, `Subscription`, `EventStore`, and `Transport` use one
asynchronous convention rather than returning either an immediate value or an
awaitable. `close()` is asynchronous and idempotent. This gives later network and
database integrations one lifecycle model without runtime return-type inspection.

### Positions are opaque

An event-store position is a string meaningful only to the store that returned it.
`read(after=position)` excludes that position. Implementations must provide an
ordered snapshot and isolate stored values from later caller mutation.

The reference `InMemoryEventStore` uses decimal offsets internally, but callers
must not parse or construct them. It copies events on append and read, supports
concurrent threads, and rejects operations after shutdown. It is volatile and is
not evidence of durability or cross-process ordering.

### Codecs preserve public event values

A `Codec` round trip preserves `type`, `payload`, `metadata`, and `tags`; propagation
state and Python identity are not serialized. Invalid documents raise `CodecError`.
`JsonCodec` is deterministic for equivalent JSON-compatible events and defines the
reference JSON shape, but it does not yet define schema evolution or wire-version
negotiation.

## Validation layers

1. `tests/contract_typing.py` is checked by strict mypy and proves structural
   signature compatibility for shipped references.
2. Runtime capability tests guard the `@runtime_checkable` surface.
3. Reusable codec and store exercises validate round trips, cursor exclusion,
   snapshot isolation, error translation, and idempotent lifecycle shutdown.

## Deferred validation

Redis Pub/Sub now validates publication, consumption, cancellation cleanup,
serialization, and shared-client ownership against its transport contracts.
Operational reconnect and load behavior still require longer-running validation.
PostgreSQL durability, transactions, and cross-process ordering likewise await a
real backend. These protocols remain provisional until those integrations pass the
same conformance model with integration services.
