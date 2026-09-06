# Production readiness

Eventful 0.3 is production-capable within the boundaries below. The project is
still pre-1.0: documented deprecations precede compatibility breaks, but the API
is not yet permanently frozen.

## Supported deployment envelope

| Component | Supported use | Delivery/durability boundary |
| --- | --- | --- |
| `EventBus` / `InMemoryBus` | One Python process; concurrent threads; sync or async listeners | In-memory, no crash recovery |
| `RedisTransport` | Cross-process live fan-out with Redis 5–6 clients | At-most-once Pub/Sub; no replay |
| `PostgresPersistence` | Durable append/replay with PostgreSQL 16 | Transactional records; caller owns retry and retention policy |
| `FilePersistence` | One process with a local filesystem | Flushes each record; no multi-process coordination or fsync guarantee |
| FastAPI / Starlette adapters | Supported framework extras and ASGI lifespan | Adapter-created buses are isolated and closed exactly once |

Python 3.13 and 3.14 are tested from both wheels and source distributions. Core
installation does not import or install optional integration dependencies.

## Release gates

Every change must pass linting, strict contract typing, the complete unit suite,
service-backed Redis and PostgreSQL tests, documentation validation, wheel/sdist
builds, and clean-install smoke tests on both supported Python versions. Security
automation performs dependency auditing and CodeQL analysis. Version tags are
published only through the protected `pypi` GitHub environment and produce signed
artifact attestations.

## Operator responsibilities

- Pin Eventful and integration dependencies in application lock files.
- Set explicit connection URLs; secure Redis/PostgreSQL with network policy,
  authentication, TLS, backup, retention, and monitoring appropriate to the system.
- Install an application error handler and observability provider. Alert on
  listener, serialization, transport, and persistence failures.
- Use PostgreSQL (or another durable `EventStore`) when loss or replay matters.
- Exercise shutdown, dependency outage, retry, and restore procedures before launch.
- Treat event payloads as application data: Eventful does not encrypt, redact,
  authorize, or classify them.

## Explicit non-guarantees

Eventful does not provide exactly-once delivery, distributed transactions,
multi-process file locking, schema evolution, dead-letter queues, broker access
control, or automatic retry policy. Applications requiring those properties must
compose them at their own boundary or use a transport/store that supplies them.

Security reports follow `SECURITY.md`; API removals follow `DEPRECATION.md`.
