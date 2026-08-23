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

```python
import asyncio

from eventful import Event
from eventful.transports.redis import RedisTransport


async def main() -> None:
    async with RedisTransport("redis://localhost:6379/0") as transport:
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

The transport relies on redis-py's connection retry and Pub/Sub resubscription
behavior. Redis client options may be passed as keyword arguments to
`RedisTransport` and are forwarded to `redis.asyncio.Redis.from_url`. Terminal
client errors become `TransportError` with the original exception retained as the
cause. Task cancellation remains `asyncio.CancelledError` and triggers consumer
cleanup.

Automatic reconnection does not change the at-most-once delivery model: messages
sent while disconnected may be lost.

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
