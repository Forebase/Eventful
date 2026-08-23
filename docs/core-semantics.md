# Core dispatch semantics

This page defines the intended 0.2 behavior of the local in-memory API. The test
suite treats these rules as compatibility requirements within the 0.2 line.

| Concern | Behavior |
| --- | --- |
| Listener selection | A lock-protected snapshot is captured before callbacks run. |
| Ordering | Descending priority, then registration order. |
| Awaiting | `emit_sync` rejects awaitables; `emit_async` awaits them sequentially. |
| Results | Successful return values only, in invocation order. |
| Listener failure | Log and continue, unless a custom error handler raises. |
| Filter failure | Escapes before dispatch because listener selection did not complete. |
| `once` | Removed before invocation; a failing or recursive callback still runs once. |
| Propagation | Stops later callbacks only when propagation control is enabled. |
| Nested emission | Depth-first; the nested dispatch completes before the outer resumes. |
| Mutation during dispatch | Affects later emissions, not the active snapshot. |
| Duplicate registration | Allowed and invoked independently. |
| Unregistration | Removes the first matching registration and returns a boolean. |
| Threading | Registration and snapshots are protected; callbacks may overlap across threads. |

## Ownership boundary

The local bus owns routing state but not application callback resources. It does
not schedule callback concurrency, retry failures, copy events, serialize payloads,
persist data, or provide cross-process delivery. Those responsibilities belong to
applications or future middleware, store, and transport implementations.

## Compatibility method

`emit(..., async_=None)` remains available for the 0.1-style facade. Its return type
depends on whether the selected snapshot contains a function declared with
`async def`. New code should use `emit_sync` or `emit_async` so the calling
convention is visible and stable.
