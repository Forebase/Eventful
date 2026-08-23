"""Keep documentation examples executable against local and optional services."""

from __future__ import annotations

import asyncio
import os

import pytest

from examples import (
    fastapi_example,
    local_dispatch,
    postgres_persistence,
    redis_pubsub,
    starlette_example,
)
from examples.request_app import request_json


def test_local_example() -> None:
    """Execute the standalone local example rather than reproducing it."""
    assert local_dispatch.main() == ["created Alice"]


@pytest.mark.redis_integration
def test_redis_example_against_service() -> None:
    """Run the documented Redis program against the configured service."""
    if "EVENTFUL_REDIS_URL" not in os.environ:
        pytest.skip("EVENTFUL_REDIS_URL is not configured")
    received = asyncio.run(redis_pubsub.main())
    assert received.type == "example.user.created"
    assert received.payload == {"id": 7}


@pytest.mark.postgres_integration
def test_postgres_example_against_service() -> None:
    """Run the documented PostgreSQL program against the configured service."""
    if "EVENTFUL_POSTGRES_URL" not in os.environ:
        pytest.skip("EVENTFUL_POSTGRES_URL is not configured")
    position, received = asyncio.run(postgres_persistence.main())
    assert int(position) >= 1
    assert received.type == "example.recorded"


@pytest.mark.parametrize(
    ("app", "expected"),
    [
        (fastapi_example.app, {"eventful": True}),
        (starlette_example.app, {"eventful": True}),
    ],
)
def test_framework_example_request(app: object, expected: dict[str, bool]) -> None:
    """Validate each exported example application through an actual ASGI request."""
    assert asyncio.run(request_json(app, "/health")) == (200, expected)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("document", "example"),
    [
        ("docs/quickstart.md", "examples/local_dispatch.py"),
        ("docs/redis.md", "examples/redis_pubsub.py"),
        ("docs/postgres.md", "examples/postgres_persistence.py"),
        ("docs/frameworks.md", "examples/fastapi_example.py"),
        ("docs/frameworks.md", "examples/starlette_example.py"),
    ],
)
def test_documentation_links_to_runnable_source(document: str, example: str) -> None:
    """Require every documented integration to identify its canonical program."""
    with open(document, encoding="utf-8") as stream:
        assert example in stream.read()
