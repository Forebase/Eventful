"""
Configuration management for eventful.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


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
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> EventfulConfig:
        """
        Create config from environment variables.

        Returns
        -------
        EventfulConfig
            Config populated from environment
        """
        config = cls()

        # Update from environment variables
        for field_name in cls.__dataclass_fields__:  # type: ignore
            env_var = f"EVENTFUL_{field_name.upper()}"
            if env_var in os.environ:
                value = os.environ[env_var]
                field_type = cls.__dataclass_fields__[field_name].type

                # Basic type conversion
                if field_type is bool:
                    value = value.lower() in ('true', '1', 'yes')
                elif field_type is int:
                    value = int(value)
                elif field_type is float:
                    value = float(value)

                setattr(config, field_name, value)

        return config


# Global config instance
_global_config: Optional[EventfulConfig] = None


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
