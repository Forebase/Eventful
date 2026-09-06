# Changelog

## 0.3.0 - unreleased

- Added deterministic ASGI ownership and shutdown behavior, including failed startup.
- Added release gates for supported Python versions, built distributions, optional
  integrations, dependency vulnerabilities, and static security analysis.
- Added a tag-only trusted-publishing workflow with artifact attestations.
- Bounded optional dependency compatibility ranges and documented production
  guarantees, limitations, support policy, and operator responsibilities.

## 0.2.0 - 2026-08-23

- Repaired package imports and packaging metadata.
- Established provisional v1 topology and contracts.
- Added repository governance, documentation, CI, and annotation policy.
- Specified explicit synchronous and asynchronous local dispatch semantics.
- Added public-boundary documentation enforcement and core behavior coverage.
- Refined architectural contracts around explicit async I/O lifecycles.
- Added JSON codec and in-memory event-store conformance references.
- Added an asynchronous Redis Pub/Sub transport with explicit at-most-once delivery,
  endpoint lifecycle, serialization validation, and service-backed integration tests.
- Added durable PostgreSQL append/replay with migrations, idempotency, optimistic
  concurrency, bounded snapshot streaming, and service-backed integration tests.
- Added FastAPI/Starlette request-state and lifespan adapters with explicit ownership.
- Integrated middleware, schema validation, observability, configuration sources,
  and plugin management as provisional cross-cutting extension paths.
