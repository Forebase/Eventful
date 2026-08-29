from __future__ import annotations
import importlib
from pathlib import Path
import pytest


def test_minimal_root_imports() -> None:
    import eventful

    assert eventful.__version__ == "0.3.0"
    assert "emit_sync" in eventful.__all__
    assert "emit_async" in eventful.__all__
    assert "AsyncDispatchRequired" in eventful.__all__
    assert "RedisBus" not in eventful.__all__


def test_no_src_eventful_imports() -> None:
    offenders = []
    for path in Path("src/eventful").rglob("*.py"):
        text = path.read_text()
        if "src.eventful" in text:
            offenders.append(str(path))
    assert offenders == []


def test_v1_topology_imports() -> None:
    for name in [
        "eventful.contracts",
        "eventful.codecs",
        "eventful.stores",
        "eventful.transports",
        "eventful.plugins",
        "eventful.configuration",
        "eventful.schemas",
        "eventful.observability",
        "eventful.middleware",
    ]:
        importlib.import_module(name)


def test_missing_redis_extra_error(monkeypatch) -> None:
    from eventful import OptionalDependencyError
    from eventful.transports.redis import RedisTransport

    def missing(*args):
        raise OptionalDependencyError("RedisTransport", "redis", "redis.asyncio")

    monkeypatch.setattr("eventful.transports.redis.require_optional", missing)
    with pytest.raises(OptionalDependencyError, match="RedisTransport"):
        RedisTransport("redis://localhost:6379")
