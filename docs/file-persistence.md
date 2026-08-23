# File persistence (provisional)

`FilePersistence` is a completed provisional backend for small, single-process
deployments. It uses only the Python standard library; the `eventful[file]` extra is
available for explicit component installs but adds no dependencies.

```python
from eventful import Event
from eventful.persistence import FilePersistence

with FilePersistence("events.jsonl", max_size=10_000_000, backup_count=5) as store:
    store.append(Event("user.created", {"id": 7}, tags={"audit"}))
    events = list(store.replay(start_id=0, batch=100))
```

## Wire format and replay

Each physical line is one UTF-8 JSON object followed by LF, with exactly the keys
`metadata`, `payload`, `tags`, and `type`. Encoding uses sorted object keys, compact
separators, unescaped Unicode, rejects non-finite floats, and sorts event tags. The
format never changes according to installed ambient packages.
Replay also accepts records produced by the earlier backend, which have the same
four event fields plus a `timestamp`; new appends never emit that legacy field.

`start_id` is a zero-based **physical line offset across retained files**, oldest to
newest. A malformed JSON line or malformed event object is logged and skipped, but
still consumes one offset. `batch` limits the number of valid events yielded, not
the number of physical records inspected. Replay is a retained-log view: rotation
may discard offsets in the oldest backup, and offsets are then renumbered from zero.

Rotation happens after an append makes the active file at least `max_size` bytes.
Backups are numbered `.1` (newest) through `.N` (oldest), and replay reads the
oldest backup first and the active file last. Both `max_size` and `backup_count`
must be positive integers; `start_id` must be a non-negative integer and `batch`
must be a positive integer.

## Concurrency, lifecycle, and failures

A re-entrant thread lock serializes append, rotation, replay, and close transitions.
Replay holds that lock until its iterator is exhausted or closed, producing a
consistent in-process view. The backend deliberately provides **no inter-process
locking**; use PostgreSQL when multiple processes or hosts write the same stream.

`close()` is idempotent and permanent. Append, replay iteration, and context entry
after close raise `StoreError`. Serialization, UTF-8 decoding, file opening,
reading, writing, rotation, and close failures are also normalized to `StoreError`
with the original failure retained as `__cause__`.
