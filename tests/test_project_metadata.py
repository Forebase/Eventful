from pathlib import Path
import tomllib

from eventful.config import EventfulConfig


def test_dev_extra_includes_docs_build_tooling() -> None:
    """CI installs the dev extra before running MkDocs."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert any(dependency.startswith("mkdocs") for dependency in dev_dependencies)


def test_environment_configuration_converts_declared_types(monkeypatch) -> None:
    monkeypatch.setenv("EVENTFUL_ENABLE_PRIORITIES", "no")
    monkeypatch.setenv("EVENTFUL_FILE_MAX_SIZE", "2048")
    monkeypatch.setenv("EVENTFUL_REDIS_RECONNECT_BACKOFF", "2.5")
    monkeypatch.setenv("EVENTFUL_REDIS_CHANNEL", "events")

    config = EventfulConfig.from_env()

    assert config.enable_priorities is False
    assert config.file_max_size == 2048
    assert config.redis_reconnect_backoff == 2.5
    assert config.redis_channel == "events"
