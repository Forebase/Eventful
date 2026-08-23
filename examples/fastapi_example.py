"""FastAPI adapter example.

Prerequisite: ``pip install -e '.[fastapi]'``.
Run once and exit: ``python -m examples.fastapi_example``
Serve manually: ``uvicorn examples.fastapi_example:app``
"""

import asyncio
from typing import Any

from fastapi import Depends, FastAPI

from eventful import EventBus, InMemoryBus
from eventful.adapters.fastapi import event_bus_dependency, install_eventful

app = FastAPI()
bus = InMemoryBus()
install_eventful(app, bus=bus)


@app.get("/health")
def health(event_bus: EventBus = Depends(event_bus_dependency())) -> dict[str, bool]:
    return {"eventful": event_bus is bus}


async def main() -> tuple[int, dict[str, Any]]:
    """Make one ASGI request to the example application without a server."""
    from examples.request_app import request_json

    response = await request_json(app, "/health")
    print(response)
    return response


if __name__ == "__main__":
    status, body = asyncio.run(main())
    assert status == 200 and body == {"eventful": True}
