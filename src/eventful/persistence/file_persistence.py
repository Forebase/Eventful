"""
File-based event persistence with rotation.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Iterator, Optional, Union
from pathlib import Path

try:
    import orjson
except ImportError:
    orjson = None

from eventful.event import Event


class FilePersistence:
    """
    File-based event persistence with log rotation.

    Uses MessagePack via orjson if available, falls back to JSON.
    """

    def __init__(
            self,
            file_path: Union[str, Path],
            max_size: int = 10 * 1024 * 1024,
            backup_count: int = 5
    ):
        """
        Initialize file persistence.

        Parameters
        ----------
        file_path : str | Path
            Path to the event log file.
        max_size : int, optional
            Maximum file size in bytes before rotation.
        backup_count : int, optional
            Number of backup files to keep.
        """
        self.file_path = Path(file_path)
        self.max_size = max_size
        self.backup_count = backup_count
        self._file = None
        self._current_size = 0
        self._lock = None  # Would use threading.Lock for thread safety

        # Create directory if needed
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> None:
        """
        Append an event to the file.

        Parameters
        ----------
        event : Event
            Event to append.
        """
        if self._file is None:
            mode = 'ab' if orjson else 'a'
            self._file = open(self.file_path, mode)
            self._current_size = self.file_path.stat().st_size if self.file_path.exists() else 0

        event_data = {
            'type': event.type,
            'payload': event.payload,
            'metadata': event.metadata,
            'tags': list(event.tags),
            'timestamp': time.time()
        }

        if orjson:
            data = orjson.dumps(event_data)
            self._file.write(data + b'\n')
        else:
            data = json.dumps(event_data) + '\n'
            self._file.write(data)

        self._current_size += len(data)
        self._file.flush()

        # Rotate if needed
        if self._current_size >= self.max_size:
            self._rotate()

    def _rotate(self) -> None:
        """Rotate the log file when it reaches max size."""
        if self._file:
            self._file.close()
            self._file = None

        if not self.file_path.exists():
            return

        # Rotate existing backup files
        for i in range(self.backup_count, 0, -1):
            old_path = self.file_path.with_suffix(f".{i}")
            if old_path.exists():
                if i == self.backup_count:
                    old_path.unlink()  # Remove oldest backup
                else:
                    new_path = self.file_path.with_suffix(f".{i + 1}")
                    old_path.rename(new_path)

        # Move current file to backup
        backup_path = self.file_path.with_suffix(".1")
        self.file_path.rename(backup_path)

        self._current_size = 0
        mode = 'ab' if orjson else 'a'
        self._file = open(self.file_path, mode)

    def replay(self, start_id: int = 0, batch: int = 1000) -> Iterator[Event]:
        """
        Replay events from the file.

        Parameters
        ----------
        start_id : int, optional
            Starting offset (not actual IDs, since file doesn't have IDs).
        batch : int, optional
            Batch size for iteration.

        Yields
        ------
        Event
            Events in chronological order.
        """
        # File persistence doesn't have IDs, so we use line numbers as pseudo-IDs
        current_line = 0
        batch_count = 0

        if not self.file_path.exists():
            return

        # Read all backup files in order
        files_to_read = [self.file_path]
        for i in range(1, self.backup_count + 1):
            backup_file = self.file_path.with_suffix(f".{i}")
            if backup_file.exists():
                files_to_read.append(backup_file)

        # Read files from oldest to newest
        for file_path in reversed(files_to_read):
            mode = 'rb' if orjson else 'r'
            with open(file_path, mode) as f:
                for line in f:
                    if current_line < start_id:
                        current_line += 1
                        continue

                    try:
                        if orjson:
                            event_data = orjson.loads(line)
                        else:
                            event_data = json.loads(line)

                        event = Event(
                            type=event_data['type'],
                            payload=event_data['payload'],
                            metadata=event_data['metadata'],
                            tags=set(event_data['tags'])
                        )
                        yield event

                        batch_count += 1
                        if batch_count >= batch:
                            return

                    except (json.JSONDecodeError, KeyError) as e:
                        logging.warning(f"Failed to parse event from file: {e}")
                        continue

                    current_line += 1

    def close(self) -> None:
        """Close the file handle."""
        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
