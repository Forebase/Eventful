# Cross-cutting extension points

Eventful provides dependency-free reference paths for middleware, schema validation,
observability, configuration, and plugins. These APIs remain provisional but are
integrated with the local bus and checked against their architectural contracts.

## Listener middleware

Middleware wraps each listener independently. The first registered middleware is
outermost:

```python
from eventful import Event, EventBus


def add_context(event, next_handler):
    event.metadata["source"] = "local"
    return next_handler(event)


bus = EventBus(middleware=(add_context,))
```

`add_middleware` and `remove_middleware` affect later listener snapshots. Explicit
sync dispatch rejects awaitable middleware results; compatibility dispatch selects
async mode when a middleware function is declared async. Async dispatch normalizes
the next-handler boundary so async middleware can await synchronous or asynchronous
listeners.

Middleware failures follow listener error policy: they are reported to the custom
error handler or logged, and dispatch continues to the next selected listener.

## Schema validation

```python
from eventful.schemas import InMemorySchemaRegistry

schemas = InMemorySchemaRegistry()
schemas.register("user.created", lambda event: "id" in event.payload)
bus.set_schema_registry(schemas)
```

Validation occurs before listener selection, filters, middleware, or once-listener
claims. A validator may implement `EventSchema.validate(event)` or be a callable
returning `False` for rejection. Failures become `SchemaValidationError`. Missing
schemas allow the event; this is an opt-in registry, not a closed-world policy.

## Observability

```python
from eventful.observability import InMemoryObservabilityProvider

observations = InMemoryObservabilityProvider()
bus.add_observability_provider(observations)
```

Providers receive best-effort `dispatch.started`, `dispatch.completed`,
`dispatch.failed`, `listener.failed`, and `schema.failed` signals. Provider failures
are logged and never change dispatch results. `InMemoryObservabilityProvider` copies
attributes into immutable records for tests; it is not a metrics backend and does
not retain event payloads.

## Configuration sources

```python
from eventful.config import EventfulConfig
from eventful.configuration import CompositeSource, EnvironmentSource, MappingSource

source = CompositeSource(
    (MappingSource({"max_queue_size": 100}), EnvironmentSource("EVENTFUL_"))
)
config = EventfulConfig.from_mapping(source.load())
```

Sources return immutable snapshots. Later composite sources win. Environment values
remain strings until `EventfulConfig.from_mapping` performs declared scalar
conversion. Unknown values enter `config.extra` by default or fail with
`allow_extra=False`. Sources never mutate global configuration.

## Plugins

`PluginManager` enforces unique, non-empty names and applies settings under each
plugin's name. Registration is explicit and deterministic. Calling
`discover("eventful.plugins")` loads Python entry points and executes third-party
code; applications should discover only trusted installed distributions.

Plugin configuration failures propagate to the caller. The manager does not define
startup/shutdown hooks yet; plugins that own resources should expose those resources
through an application lifespan boundary.
