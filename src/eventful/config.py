"""
Configuration management for eventful.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from typing import Any, get_type_hints

from .exceptions import ConfigurationError


@dataclass
class EventfulConfig:
    """
    Configuration for eventful components.
    """

    # Bus configuration
    enable_priorities: bool = True
    propagation_enabled: bool = True

    # Redis transport
    redis_url: str = "redis://localhost:6379"
    redis_channel: str = "eventful"
    redis_reconnect_backoff: float = 1.0

    # File persistence
    file_path: str = "events.log"
    file_max_size: int = 10 * 1024 * 1024  # 10MB
    file_backup_count: int = 5

    # PostgreSQL persistence
    postgres_url: str = "postgresql://localhost:5432/eventful"
    postgres_table: str = "events"

    # Logging
    logging_enabled: bool = True
    logging_level: str = "INFO"

    # Performance
    max_queue_size: int = 10000

    # Additional custom settings
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> EventfulConfig:
        """
        Create config from environment variables.

        Returns
        -------
        EventfulConfig
            Config populated from environment
        """
        values = {
            config_field.name: os.environ[f"EVENTFUL_{config_field.name.upper()}"]
            for config_field in fields(cls)
            if f"EVENTFUL_{config_field.name.upper()}" in os.environ
        }
        return cls.from_mapping(values)

    @classmethod
    def from_mapping(
        cls, values: Mapping[str, Any], *, allow_extra: bool = True
    ) -> EventfulConfig:
        """Create typed configuration from a mapping without mutating it.

        Unknown keys are copied into `extra` by default or rejected when
        `allow_extra` is false. String values for bool, int, and float fields are
        converted according to their declared dataclass types.
        """
        known = {config_field.name for config_field in fields(cls)}
        type_hints = get_type_hints(cls)
        arguments: dict[str, Any] = {}
        extras: dict[str, Any] = {}
        for key, raw_value in values.items():
            if key not in known:
                if not allow_extra:
                    raise ConfigurationError(f"unknown configuration key: {key!r}")
                extras[key] = raw_value
                continue
            if key == "extra":
                if not isinstance(raw_value, Mapping):
                    raise ConfigurationError("configuration 'extra' must be a mapping")
                extras.update(raw_value)
                continue
            arguments[key] = cls._coerce_value(key, raw_value, type_hints[key])
        arguments["extra"] = extras
        return cls(**arguments)

    @staticmethod
    def _coerce_value(name: str, value: Any, target: object) -> Any:
        """Convert supported scalar strings with descriptive boundary errors."""
        if not isinstance(value, str) or target is str:
            return value
        try:
            if target is bool:
                normalized = value.lower()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
                raise ValueError("expected a boolean")
            if target is int:
                return int(value)
            if target is float:
                return float(value)
        except ValueError as exc:
            raise ConfigurationError(
                f"invalid value for configuration {name!r}: {value!r}"
            ) from exc
        return value


# Global config instance
_global_config: EventfulConfig | None = None


def get_config() -> EventfulConfig:
    """
    Get the global configuration instance.

    Returns
    -------
    EventfulConfig
        Global configuration
    """
    global _global_config
    if _global_config is None:
        _global_config = EventfulConfig.from_env()
    return _global_config


def set_config(config: EventfulConfig) -> None:
    """
    Set the global configuration.

    Parameters
    ----------
    config : EventfulConfig
        New global configuration
    """
    global _global_config
    _global_config = config
