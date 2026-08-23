# Eventful documentation

## Vision and scope

Eventful aims to become a small library, framework integration layer, and development kit for event-driven Python applications. Version 0.2 is a foundation release: it keeps the useful alpha in-memory dispatcher while establishing the package map and contracts expected for v1.

## Library, framework, development kit

- **Library:** local dispatch primitives that work without optional dependencies.
- **Framework adapters:** optional FastAPI/Starlette integration points.
- **Development kit:** contracts and extension seams for transports, stores, codecs, plugins, schemas, configuration, and observability.

## Semantics

- **Local dispatcher:** in-process listener routing; no durability or cross-process delivery.
- **Broker transport:** future integration for Redis or other brokers; delivery depends on broker behavior.
- **Durable store:** provisional PostgreSQL append/replay with opaque positions,
  explicit migrations, and deployment-owned operational durability.

## Package map

| Package | Status | Purpose |
| --- | --- | --- |
| `eventful` | provisional | 0.1-compatible facade and local bus |
| `eventful.contracts` | provisional | typed, runtime-checkable component boundaries |
| `eventful.codecs` | provisional | codec contract and JSON conformance reference |
| `eventful.stores` | provisional | event-store contract and volatile conformance reference |
| `eventful.transports` | provisional | Redis Pub/Sub transport with at-most-once delivery |
| `eventful.persistence` | provisional | file and durable PostgreSQL event stores |
| `eventful.adapters` | provisional | FastAPI/Starlette request state and lifespan ownership |
| `eventful.middleware` | provisional | ordered per-listener middleware chain |
| `eventful.plugins` | provisional | explicit plugin management and opt-in discovery |
| `eventful.configuration` | provisional | immutable and composable configuration sources |
| `eventful.schemas` | provisional | exact-type schema validation registry |
| `eventful.observability` | provisional | isolated dispatch instrumentation providers |

## Public API policy

Until 1.0, APIs are stable only when explicitly marked stable. Provisional APIs may change with deprecation warnings where practical. Experimental APIs may change or be removed in minor releases.

## Extension model

Extensions should implement the Protocols in `eventful.contracts`, pass the relevant behavioral conformance suite, and raise component-specific errors when optional dependencies are missing. See [architectural contracts](contracts.md) for lifecycle and validation decisions.

## Configuration philosophy

Minimal installs use dataclass configuration and environment variables. Richer configuration sources belong behind `ConfigurationSource` contracts.

## Terminology

An **event** has a type, payload, metadata, and tags. **Delivery** means invoking matching local listeners in dispatch order. **Publication** means handing an event to a bus, broker, or stream.

## Reliability and security

Local dispatch is best-effort and process-local. Durable claims require explicit store contracts, acknowledgements, replay semantics, validation, and security review.

## Roadmap

- **0.2:** repair packaging, establish topology, document status.
- **0.3-0.5:** fill codecs, middleware, configuration, and observability.
- **0.6-0.8:** integrate broker/store implementations with tests.
- **0.9:** API freeze candidates and migration tooling.
- **1.0:** stable documented facade.

## Non-goals

Eventful 0.2 does not claim exactly-once distributed delivery, automatic PostgreSQL
operations, Redis Streams durability, or performance benchmarks. PostgreSQL commit
durability and availability depend on deployment configuration.

## Development workflow

Run `python -m pip install -e '.[dev]'`, then `python scripts/check_quality.py` to execute the same checks as CI.
