"""Persistence namespace for provisional and experimental stores."""
from __future__ import annotations
from eventful.api_status import ApiStatus
from .file_persistence import FilePersistence
API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "FilePersistence"]
