"""Standard-library JSON reference implementation of the codec contract.

The codec serializes only the public :class:`eventful.event.Event` fields. It does
not encode propagation state, Python object identity, schema versions, or arbitrary
non-JSON payloads; richer formats belong in separate codec implementations.
"""

from __future__ import annotations

import json
from typing import Any

from eventful.event import Event
from eventful.exceptions import CodecError


class JsonCodec:
    """Round-trip JSON-compatible events as deterministic UTF-8 bytes."""

    media_type = "application/json"

    def encode(self, event: Event) -> bytes:
        """Encode all public event fields or raise :class:`CodecError`."""
        if not isinstance(event, Event):
            raise TypeError("event must be an Event")
        document = {
            "type": event.type,
            "payload": event.payload,
            "metadata": event.metadata,
            "tags": sorted(event.tags),
        }
        try:
            return json.dumps(
                document,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CodecError(f"event is not JSON serializable: {exc}") from exc

    def decode(self, data: bytes) -> Event:
        """Decode and validate a complete event document or raise `CodecError`."""
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        try:
            raw: Any = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CodecError(f"invalid JSON event: {exc}") from exc

        if not isinstance(raw, dict):
            raise CodecError("JSON event must be an object")
        event_type = raw.get("type")
        metadata = raw.get("metadata", {})
        tags = raw.get("tags", [])
        if not isinstance(event_type, str) or not event_type:
            raise CodecError("JSON event 'type' must be a non-empty string")
        if not isinstance(metadata, dict) or not all(
            isinstance(key, str) for key in metadata
        ):
            raise CodecError("JSON event 'metadata' must be an object")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise CodecError("JSON event 'tags' must be an array of strings")
        return Event(
            type=event_type,
            payload=raw.get("payload"),
            metadata=metadata,
            tags=set(tags),
        )
