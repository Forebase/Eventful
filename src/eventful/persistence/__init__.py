"""Persistence namespace for file and PostgreSQL event stores.

PostgreSQL is an optional durable backend; importing this namespace does not create
connections or require asyncpg until `PostgresPersistence` is instantiated.
"""

from __future__ import annotations
from eventful.api_status import ApiStatus
from .file_persistence import FilePersistence
from .postgres_persistence import PostgresPersistence

API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "FilePersistence", "PostgresPersistence"]
