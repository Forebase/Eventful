"""Persistence namespace for provisional file and PostgreSQL event stores.

The file backend is dependency-free. PostgreSQL is optional; importing this
namespace does not create connections or require asyncpg until
`PostgresPersistence` is instantiated.
"""

from __future__ import annotations
from eventful.api_status import ApiStatus
from .file_persistence import FilePersistence
from .postgres_persistence import PostgresPersistence

API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "FilePersistence", "PostgresPersistence"]
