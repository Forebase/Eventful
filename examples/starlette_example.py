"""Starlette adapter example.

Prerequisite: ``pip install -e '.[starlette]'``.
Run once and exit: ``python -m examples.starlette_example``
Serve manually: ``uvicorn examples.starlette_example:app``
"""

import asyncio
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from eventful import InMemoryBus
from eventful.adapters.starlette import add_eventful_middleware, request_event_bus

bus = InMemoryBus()


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"eventful": request_event_bus(request) is bus})


app = Starlette(routes=[Route("/health", health)])
add_eventful_middleware(app, bus=bus)


async def main() -> tuple[int, dict[str, Any]]:
    """Make one ASGI request to the example application without a server."""
    from examples.request_app import request_json

    response = await request_json(app, "/health")
    print(response)
    return response


if __name__ == "__main__":
    assert asyncio.run(main()) == (200, {"eventful": True})
