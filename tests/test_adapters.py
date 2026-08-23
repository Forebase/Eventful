"""Framework lifecycle and request-isolation tests for optional adapters."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from fastapi import Depends, FastAPI, Request

from eventful import EventBus
from eventful.adapters.fastapi import event_bus_dependency, install_eventful
from eventful.adapters.starlette import EventfulMiddleware, request_event_bus


class CloseableBus(EventBus):
    """Track asynchronous adapter-driven shutdown."""

    def __init__(self) -> None:
        """Create an open local bus."""
        super().__init__()
        self.closed = False

    async def close(self) -> None:
        """Mark the test bus closed."""
        self.closed = True


async def terminal_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Complete HTTP or lifespan ASGI interactions for middleware tests."""
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


async def invoke_http(middleware: EventfulMiddleware) -> dict[str, Any]:
    """Invoke one minimal HTTP ASGI scope and return attached state."""
    scope: dict[str, Any] = {"type": "http"}

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        return None

    await middleware(scope, receive, send)
    return scope["state"]


async def invoke_lifespan(middleware: EventfulMiddleware) -> list[str]:
    """Run startup and shutdown and return sent ASGI message types."""
    messages = iter(({"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}))
    sent: list[str] = []

    async def receive() -> dict[str, str]:
        return next(messages)

    async def send(message: dict[str, str]) -> None:
        sent.append(message["type"])

    await middleware({"type": "lifespan"}, receive, send)
    return sent


async def invoke_fastapi(app: FastAPI, path: str) -> tuple[int, dict[str, Any]]:
    """Issue one dependency-free HTTP ASGI request to a FastAPI application."""
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("test", 1),
        "server": ("test", 80),
    }
    sent: list[dict[str, Any]] = []
    received = False

    async def receive() -> dict[str, Any]:
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await app(scope, receive, send)
    start = next(
        message for message in sent if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(body)


def test_starlette_attaches_one_bus_without_global_fallback() -> None:
    """Expose an injected app bus through isolated request state."""
    bus = CloseableBus()
    middleware = EventfulMiddleware(terminal_app, bus=bus)

    state = asyncio.run(invoke_http(middleware))
    request = SimpleNamespace(state=SimpleNamespace(**state))

    assert request_event_bus(request) is bus
    assert bus.closed is False


def test_lifespan_respects_external_and_explicit_ownership() -> None:
    """Close an injected resource only when ownership is explicit."""
    external = CloseableBus()
    external_middleware = EventfulMiddleware(terminal_app, bus=external)
    assert asyncio.run(invoke_lifespan(external_middleware)) == [
        "lifespan.startup.complete",
        "lifespan.shutdown.complete",
    ]
    assert external.closed is False

    owned = CloseableBus()
    owned_middleware = EventfulMiddleware(
        terminal_app, bus=owned, close_on_shutdown=True
    )
    asyncio.run(invoke_lifespan(owned_middleware))
    assert owned.closed is True


def test_fastapi_installs_middleware_and_dependency_uses_request_state() -> None:
    """Use FastAPI's middleware registry and Request annotation contract."""
    app = FastAPI()
    bus = CloseableBus()
    install_eventful(app, bus=bus)
    dependency = event_bus_dependency()
    request = SimpleNamespace(state=SimpleNamespace(eventful_bus=bus))

    @app.get("/bus")
    def bus_endpoint(resolved: EventBus = Depends(dependency)):
        return {"same": resolved is bus}

    assert app.user_middleware[0].cls is EventfulMiddleware
    assert dependency(request) is bus
    assert dependency.__annotations__["request"] is Request
    assert asyncio.run(invoke_fastapi(app, "/bus")) == (200, {"same": True})


def test_request_event_bus_requires_middleware_state() -> None:
    """Avoid silently leaking the process-global bus into unconfigured requests."""
    request = SimpleNamespace(state=SimpleNamespace())

    try:
        request_event_bus(request)
    except RuntimeError as exc:
        assert "install EventfulMiddleware" in str(exc)
    else:
        raise AssertionError("missing request state should fail")
