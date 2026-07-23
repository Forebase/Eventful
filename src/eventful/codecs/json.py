"""Provisional JSON codec using only the Python standard library."""
from __future__ import annotations
import json
from typing import Any
from eventful.event import Event
from eventful.exceptions import CodecError

class JsonCodec:
    """Encode Event objects as UTF-8 JSON."""
    media_type = "application/json"
    def encode(self, event: Event) -> bytes:
        try:
            return json.dumps({"type": event.type, "payload": event.payload, "metadata": event.metadata, "tags": sorted(event.tags)}).encode()
        except (TypeError, ValueError) as exc:
            raise CodecError(str(exc)) from exc
    def decode(self, data: bytes) -> Event:
        try:
            raw: dict[str, Any] = json.loads(data.decode())
            return Event(type=raw["type"], payload=raw.get("payload"), metadata=raw.get("metadata", {}), tags=set(raw.get("tags", [])))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CodecError(str(exc)) from exc
