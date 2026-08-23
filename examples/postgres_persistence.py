"""PostgreSQL persistence example.

Prerequisites: a writable PostgreSQL database and ``pip install -e '.[postgres]'``.
Run: ``EVENTFUL_POSTGRES_URL=postgresql://localhost/eventful python examples/postgres_persistence.py``
"""

import asyncio
import os
from uuid import uuid4

from eventful import Event
from eventful.persistence import PostgresPersistence


async def main() -> tuple[str, Event]:
    """Append and replay one uniquely identifiable event, then close the pool."""
    store = PostgresPersistence(os.environ["EVENTFUL_POSTGRES_URL"])
    await store.open()
    try:
        await store.migrate()
        event = Event("example.recorded", payload={"run_id": uuid4().hex})
        position = await store.append(event)
        replayed = [item async for item in store.read(after=str(int(position) - 1))]
        received = replayed[0]
        print(f"stored position {position}: {received.payload}")
        return position, received
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
