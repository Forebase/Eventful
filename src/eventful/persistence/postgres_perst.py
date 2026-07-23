"""Compatibility module for the misspelled alpha PostgreSQL module."""
from __future__ import annotations
import warnings
from .postgres_persistence import PostgresPersistence
warnings.warn("eventful.persistence.postgres_perst is deprecated; use postgres_persistence", DeprecationWarning, stacklevel=2)
__all__ = ["PostgresPersistence"]
