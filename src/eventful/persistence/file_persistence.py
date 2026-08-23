"""Deterministic JSON Lines event persistence with bounded rotation."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

from eventful.event import Event
from eventful.exceptions import StoreError

_EVENT_FIELDS = {"metadata", "payload", "tags", "type"}
_LEGACY_EVENT_FIELDS = _EVENT_FIELDS | {"timestamp"}


class FilePersistence:
    """Persist events as dependency-free, UTF-8 JSON Lines records.

    Physical line numbers are replay offsets. Corrupt records consume an offset
    but are skipped. This store is thread-safe within one process; it does not
    coordinate access by multiple processes.
    """

    def __init__(
        self,
        file_path: str | Path,
        max_size: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        """Create a store, validating its rotation configuration."""
        if isinstance(max_size, bool) or not isinstance(max_size, int) or max_size < 1:
            raise ValueError("max_size must be a positive integer")
        if (
            isinstance(backup_count, bool)
            or not isinstance(backup_count, int)
            or backup_count < 1
        ):
            raise ValueError("backup_count must be a positive integer")

        self.file_path = Path(file_path)
        self.max_size = max_size
        self.backup_count = backup_count
        self._file: TextIO | None = None
        self._current_size = 0
        self._lock = threading.RLock()
        self._closed = False
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StoreError(f"cannot create event log directory: {exc}") from exc

    def append(self, event: Event) -> None:
        """Append one event, or raise :class:`~eventful.exceptions.StoreError`."""
        with self._lock:
            self._ensure_open()
            if not isinstance(event, Event):
                raise StoreError("append requires an Event")
            try:
                record = json.dumps(
                    {
                        "metadata": event.metadata,
                        "payload": event.payload,
                        "tags": sorted(event.tags),
                        "type": event.type,
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                encoded_size = len(record.encode("utf-8")) + 1
            except (TypeError, ValueError, UnicodeError) as exc:
                raise StoreError(f"event cannot be serialized as JSON: {exc}") from exc

            try:
                self._open_for_append()
                assert self._file is not None
                self._file.write(record + "\n")
                self._file.flush()
                self._current_size += encoded_size
                if self._current_size >= self.max_size:
                    self._rotate()
            except (OSError, ValueError) as exc:
                raise StoreError(f"cannot append to event log: {exc}") from exc

    def replay(self, start_id: int = 0, batch: int = 1000) -> Iterator[Event]:
        """Yield at most ``batch`` valid events from physical offset ``start_id``."""
        self._validate_replay_arguments(start_id, batch)
        return self._replay(start_id, batch)

    def _replay(self, start_id: int, batch: int) -> Iterator[Event]:
        with self._lock:
            self._ensure_open()
            offset = 0
            yielded = 0
            try:
                for path in self._paths_oldest_first():
                    if not path.exists():
                        continue
                    with path.open("r", encoding="utf-8", newline="") as stream:
                        for line in stream:
                            line_offset = offset
                            offset += 1
                            if line_offset < start_id:
                                continue
                            try:
                                data = json.loads(
                                    line,
                                    parse_constant=lambda value: (_ for _ in ()).throw(
                                        ValueError(f"invalid JSON constant {value}")
                                    ),
                                )
                                if not isinstance(data, dict) or set(data) not in (
                                    _EVENT_FIELDS,
                                    _LEGACY_EVENT_FIELDS,
                                ):
                                    raise ValueError("record contains unsupported event fields")
                                if not isinstance(data["type"], str):
                                    raise ValueError("event type must be a string")
                                if not isinstance(data["metadata"], dict):
                                    raise ValueError("event metadata must be an object")
                                if not isinstance(data["tags"], list) or not all(
                                    isinstance(tag, str) for tag in data["tags"]
                                ):
                                    raise ValueError("event tags must be a string array")
                                event = Event(
                                    type=data["type"],
                                    payload=data["payload"],
                                    metadata=data["metadata"],
                                    tags=set(data["tags"]),
                                )
                            except (
                                json.JSONDecodeError,
                                KeyError,
                                RecursionError,
                                TypeError,
                                ValueError,
                            ) as exc:
                                logging.getLogger(__name__).warning(
                                    "Skipping malformed event record at offset %d: %s",
                                    line_offset,
                                    exc,
                                )
                                continue
                            yield event
                            yielded += 1
                            if yielded >= batch:
                                return
            except (OSError, UnicodeError) as exc:
                raise StoreError(f"cannot replay event log: {exc}") from exc

    def close(self) -> None:
        """Permanently close the store; repeated calls are harmless."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._file is not None:
                try:
                    self._file.close()
                except OSError as exc:
                    raise StoreError(f"cannot close event log: {exc}") from exc
                finally:
                    self._file = None

    def _ensure_open(self) -> None:
        if self._closed:
            raise StoreError("file persistence is closed")

    def _open_for_append(self) -> None:
        if self._file is None:
            self._file = self.file_path.open("a", encoding="utf-8", newline="\n")
            self._current_size = self.file_path.stat().st_size

    def _backup_path(self, number: int) -> Path:
        return self.file_path.with_suffix(f".{number}")

    def _paths_oldest_first(self) -> list[Path]:
        return [
            *(self._backup_path(i) for i in range(self.backup_count, 0, -1)),
            self.file_path,
        ]

    def _rotate(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        oldest = self._backup_path(self.backup_count)
        if oldest.exists():
            oldest.unlink()
        for number in range(self.backup_count - 1, 0, -1):
            source = self._backup_path(number)
            if source.exists():
                source.replace(self._backup_path(number + 1))
        if self.file_path.exists():
            self.file_path.replace(self._backup_path(1))
        self._current_size = 0

    @staticmethod
    def _validate_replay_arguments(start_id: int, batch: int) -> None:
        if isinstance(start_id, bool) or not isinstance(start_id, int) or start_id < 0:
            raise ValueError("start_id must be a non-negative integer")
        if isinstance(batch, bool) or not isinstance(batch, int) or batch < 1:
            raise ValueError("batch must be a positive integer")

    def __enter__(self) -> FilePersistence:
        with self._lock:
            self._ensure_open()
            return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()


__all__ = ["FilePersistence"]
