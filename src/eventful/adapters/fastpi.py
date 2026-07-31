"""Compatibility shim for the misspelled alpha FastAPI adapter module."""
from __future__ import annotations
import warnings
from .fastapi import *  # noqa: F403
warnings.warn("eventful.adapters.fastpi is deprecated; use eventful.adapters.fastapi", DeprecationWarning, stacklevel=2)
