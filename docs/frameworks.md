# FastAPI and Starlette adapters

Install the framework integration you use:

```bash
pip install 'eventful[fastapi]'
pip install 'eventful[starlette]'
```

Both adapters use the same ASGI middleware. It attaches one application bus to
HTTP and WebSocket scope state without replacing Eventful's process-global default.

## FastAPI

See [`examples/fastapi_example.py`](examples.md#fastapi) for a standalone
program that makes an application-level request and exits. The documentation test
imports its `app` and validates the real `/health` response.

```python
from fastapi import Depends, FastAPI

from eventful import EventBus, InMemoryBus
from eventful.adapters.fastapi import event_bus_dependency, install_eventful

app = FastAPI()
bus = InMemoryBus()
install_eventful(app, bus=bus)


@app.get("/health")
def health(event_bus: EventBus = Depends(event_bus_dependency())) -> dict[str, bool]:
    return {"eventful": event_bus is bus}
```

`event_bus_dependency(explicit_bus)` can pin a dependency to a bus without reading
request state. `get_event_bus` remains a compatibility helper, but request-state or
explicit dependency ownership is recommended.

## Starlette

See [`examples/starlette_example.py`](examples.md#starlette) for the
equivalent runnable Starlette application. Its exported `app` is also the object
used by the application-level documentation test.

```python
from starlette.applications import Starlette

from eventful import InMemoryBus
from eventful.adapters.starlette import add_eventful_middleware, request_event_bus

app = Starlette()
add_eventful_middleware(app, bus=InMemoryBus())


async def endpoint(request):
    bus = request_event_bus(request)
    ...
```

`request_event_bus` raises when middleware state is missing instead of silently
falling back to a process-global bus. An explicit `default=` is available when a
fallback is intentional.

## Ownership and lifespan

- An injected `bus=` remains caller-owned by default.
- A bus created by `bus_factory=` or by the middleware default is adapter-owned.
- `close_on_shutdown=True` opts an injected bus into adapter ownership.
- On `lifespan.shutdown.complete`, the adapter awaits `bus.close()` when the owned
  bus exposes a synchronous or asynchronous close method.
- Cleanup completes before shutdown success is forwarded to the ASGI server.
- A failed startup (either `lifespan.startup.failed` or an exception escaping the
  lifespan application) also closes an adapter-owned bus. Caller-owned buses remain
  untouched in every failure path.
- Cleanup is idempotent: repeated startup/shutdown cycles against the same middleware
  instance do not close a bus more than once. Create a new application/middleware
  instance to obtain a fresh adapter-owned bus after shutdown.

The local `EventBus` has no resources to close. The generic close behavior exists
for application bus subclasses that coordinate transports, stores, or plugins.

## Request isolation

The bus itself is application-scoped. Request state isolates access paths, not bus
registrations. Use separate application instances or a custom `bus_factory` when
tests or tenants require distinct registration state. `state_key=` supports
coexistence with another request-state convention.

Each middleware instance creates its own bus, so concurrently running application
instances are isolated. This is process-local isolation only: pre-fork and
multi-worker deployments create one adapter-owned bus per worker. Eventful does not
coordinate registrations or delivery between workers; inject a caller-managed
transport-backed bus when cross-process behavior is required. Do not share one
adapter-owned middleware instance between event loops.

## Supported versions

The adapters support FastAPI 0.110 or newer and Starlette 0.37 or newer on Eventful's
supported Python versions. The compatibility floor is exercised through the public
ASGI and dependency APIs; CI's normal dependency resolution also exercises current
framework releases. Major-version compatibility is not promised until separately
validated.
