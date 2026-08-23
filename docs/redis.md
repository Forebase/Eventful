# Redis Pub/Sub transport

`RedisTransport` is Eventful's first broker integration. Install it with:

```bash
pip install 'eventful[redis]'
```

The integration uses redis-py's asynchronous API and the dependency-free
`JsonCodec` by default.

## Delivery model

Each event publishes to the exact Redis channel
`<channel_prefix><event.type>`. A consumer created for `user.created` therefore
receives events whose type is exactly `user.created`; wildcard topic routing remains
a local-bus feature.

Redis Pub/Sub is **live, at-most-once fan-out**:

- Events published before subscription are not replayed.
- There are no acknowledgements or consumer offsets.
- Disconnects can lose events.
- Slow consumers depend on Redis and socket output buffers and may be disconnected.
- Ordering follows Redis Pub/Sub delivery for a single publisher/channel; Eventful
  does not create a stronger global ordering guarantee.

Use a future Redis Streams or durable event-store integration when replay,
acknowledgements, or durable delivery is required.

## Example

The standalone version, including prerequisites and an environment-variable based
connection URL, is [`examples/redis_pubsub.py`](examples.md#redis-pubsub).
The service-backed documentation test runs that file's `main` function directly.

```python
import asyncio
import os

from eventful import Event
from eventful.transports.redis import RedisTransport


async def main() -> None:
    async with RedisTransport(os.environ["EVENTFUL_REDIS_URL"]) as transport:
        consumer = transport.consumer("user.created")
        await consumer.subscribe()

        async def receive_one() -> Event:
            async for event in consumer.consume():
                return event
            raise RuntimeError("consumer closed before receiving an event")

        pending = asyncio.create_task(receive_one())
        await transport.publisher().publish(
            Event("user.created", payload={"id": 7})
        )
        received = await pending
        assert received.payload == {"id": 7}


asyncio.run(main())
```

Call `subscribe()` before signaling producer readiness. `consume()` also subscribes
lazily when explicit coordination is unnecessary.

## Lifecycle and ownership

- A transport created from a URL owns and closes its Redis client.
- An injected `client=` remains caller-owned, which supports shared infrastructure
  and deterministic tests.
- Every `consumer(topic)` owns one lazy Pub/Sub resource and allows one active
  iterator. `subscribe()` can establish it eagerly and idempotently.
- Ending or cancelling `consume()` closes that consumer permanently.
- `publisher().close()` closes the lightweight publisher endpoint, not the shared
  Redis client.
- `transport.close()` closes consumers, its publisher, and any owned client.
- All close methods are idempotent; async context management is recommended.

## Reconnection and cancellation

Eventful does **not** implement a retry queue or replay loop. It makes one public
method call and relies only on retry behavior configured in redis-py:

- `publish()` calls redis-py's `publish()` once. A reconnect/retry completed by the
  client can make that call succeed; otherwise Eventful raises `TransportError`.
  Eventful never resends after the call returns or raises, because after a lost
  response it cannot know whether Redis received the publication.
- `subscribe()` calls redis-py's `subscribe()` once. An unrecovered connection
  failure is a `TransportError`; cancellation remains `asyncio.CancelledError` and
  closes the incomplete Pub/Sub resource.
- `consume()` lets redis-py reconnect and restore its current Pub/Sub subscriptions
  while polling. An unrecovered read failure is a `TransportError` and permanently
  closes that consumer. Start a new consumer to try again.
- `close()` does not retry failed unsubscribe or close operations. It attempts all
  consumer closes before surfacing a shutdown `TransportError`, and repeated calls
  remain safe.

Redis client options may be passed as keyword arguments to `RedisTransport` and
are forwarded to `redis.asyncio.Redis.from_url`. Original client exceptions are
retained as causes. Task cancellation is never translated to `TransportError`.

Automatic reconnection does not change the at-most-once delivery model: messages
sent while disconnected may be lost. A successful `publish()` means Redis reported
the number of live subscribers; it does not mean a consumer processed, persisted,
or can replay the event. A clean connection reset can be recovered internally by
redis-py, including resubscription. In the validated default configuration, a hard
server restart surfaced the broken read as `TransportError`; callers had to create
a fresh consumer after the server returned. Either outcome leaves an unavoidable
delivery gap.

## Validated operational limits

Service-backed scenarios exercise forced publisher and subscriber connection
loss, reconnection after the service becomes available again, cancellation during
reconnection, duplicate-subscription cleanup, malformed broker messages,
concurrent bursts, and bounded deterministic shutdown. These checks establish
lifecycle and error behavior, not a durability guarantee:

- Connection recovery is bounded by redis-py's configured retry policy and the
  caller's own timeout or cancellation.
- No event count is asserted across a disconnect or restart boundary. Only events
  published after subscription readiness is re-established are expected. A hard
  restart may terminate the old consumer before redis-py's reconnect path runs.
- Concurrent publishing is safe when callers bound concurrency to the configured
  redis-py pool. A task fan-out beyond `max_connections` is surfaced as a publish
  `TransportError`; Eventful supplies no global ordering or unbounded buffering.
- Malformed data terminates only the affected consumer; it is not skipped or sent
  to a dead-letter channel.
- Shutdown is deterministic for responsive Redis connections. A stalled network
  operation still needs an application-level deadline such as `asyncio.timeout()`.

## Serialization and validation

Incoming payloads must be bytes containing a valid `JsonCodec` event. The decoded
event type must match the subscribed topic. Malformed payloads and topic mismatches
terminate that consumer with `TransportError`; they are never yielded as events.

Pass `codec=` to use another implementation of `eventful.contracts.Codec`. Both
publisher and consumers on a transport share that codec.

## Configuration

```python
RedisTransport(
    url,
    codec=JsonCodec(),
    channel_prefix="eventful:",
    poll_timeout=1.0,
    health_check_interval=30,  # forwarded to redis-py
)
```

`poll_timeout` bounds how long the consumer waits before checking lifecycle state;
it is not a delivery timeout. Additional keyword arguments are forwarded to
redis-py's URL-based client constructor. `decode_responses=False` is enforced so
codec inputs remain bytes.
