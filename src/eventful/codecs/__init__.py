"""Provisional serialization contracts and reference codecs.

`JsonCodec` is the dependency-free behavioral reference. Schema evolution and
binary codecs remain outside this package's current responsibility.
"""

from __future__ import annotations

from eventful.api_status import ApiStatus
from eventful.codecs.json import JsonCodec

API_STATUS = ApiStatus.PROVISIONAL
__all__ = ["API_STATUS", "JsonCodec"]
