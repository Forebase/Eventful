"""Redis Pub/Sub example.

Prerequisites: a running Redis server and ``pip install -e '.[redis]'``.
Run: ``EVENTFUL_REDIS_URL=redis://localhost:6379/0 python examples/redis_pubsub.py``
"""

import asyncio
import os

from eventful import Event
from eventful.transports.redis import RedisTransport


async def main() -> Event:
    """Publish and receive one event, closing all resources afterward."""
    url = os.environ["EVENTFUL_REDIS_URL"]
    async with RedisTransport(url) as transport:
        consumer = transport.consumer("example.user.created")
        await consumer.subscribe()

        async def receive_one() -> Event:
            async for event in consumer.consume():
                return event
            raise RuntimeError("consumer closed before receiving an event")

        pending = asyncio.create_task(receive_one())
        await transport.publisher().publish(
            Event("example.user.created", payload={"id": 7})
        )
        received = await asyncio.wait_for(pending, timeout=5)
        print(f"received {received.type}: {received.payload}")
        return received


if __name__ == "__main__":
    asyncio.run(main())
