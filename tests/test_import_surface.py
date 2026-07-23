from __future__ import annotations
import importlib
from pathlib import Path
import pytest


def test_minimal_root_imports() -> None:
    import eventful
    assert eventful.__version__ == "0.2.0"
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
        "eventful.contracts", "eventful.codecs", "eventful.stores",
        "eventful.transports", "eventful.plugins", "eventful.configuration",
        "eventful.schemas", "eventful.observability", "eventful.middleware",
    ]:
        importlib.import_module(name)


def test_missing_redis_extra_error() -> None:
    from eventful import OptionalDependencyError
    from eventful.transports.redis import RedisTransport
    with pytest.raises(OptionalDependencyError, match="RedisTransport"):
        RedisTransport("redis://localhost:6379")
