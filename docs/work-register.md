# Work register

All intentional incompleteness must use an annotation listed in `docs/annotation-policy.md` and include an issue link.

| Module | Status | Deferred work |
| --- | --- | --- |
| `eventful.adapters` | validated in-process ASGI lifecycle | Multi-worker delivery remains deployment-managed; major framework versions require separate validation (Issue: Forebase/Eventful#1). |
| `eventful.transports.redis` | provisional Pub/Sub | Validate operational reconnect and load behavior; Redis Streams durability remains deferred (Issue: Forebase/Eventful#2). |
| `eventful.persistence.postgres_persistence` | provisional durable store | Validate migration upgrades, retention, replication, and operational load behavior (Issue: Forebase/Eventful#3). |
| `eventful.contracts` | provisional, reference-validated | Validate async lifecycle, delivery, and durability semantics against real Redis/PostgreSQL integrations (Issue: Forebase/Eventful#4). |
