"""Behavioral tests for the dependency-free file persistence backend."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from eventful import Event
from eventful.exceptions import StoreError
from eventful.persistence import FilePersistence


def test_round_trip_is_utf8_and_deterministic(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    store = FilePersistence(path)
    event = Event("café.created", {"name": "Zoë"}, {"z": 1}, {"b", "a"})

    store.append(event)

    assert list(store.replay()) == [event]
    store.close()
    assert path.read_text(encoding="utf-8") == (
        '{"metadata":{"z":1},"payload":{"name":"Zoë"},'
        '"tags":["a","b"],"type":"café.created"}\n'
    )


def test_rotation_replays_oldest_to_newest(tmp_path) -> None:
    store = FilePersistence(tmp_path / "events.jsonl", max_size=1, backup_count=3)
    for number in range(4):
        store.append(Event("number", number))

    assert [event.payload for event in store.replay()] == [1, 2, 3]


def test_replay_offset_counts_malformed_records_and_batch_counts_events(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"metadata":{},"payload":0,"tags":[],"type":"number"}\n'
        "not-json\n"
        '{"metadata":{},"payload":2,"tags":[],"type":"number"}\n'
        '{"metadata":{},"payload":3,"tags":[],"type":"number"}\n',
        encoding="utf-8",
    )
    store = FilePersistence(path)

    assert [event.payload for event in store.replay(start_id=1, batch=1)] == [2]
    assert [event.payload for event in store.replay(start_id=2, batch=2)] == [2, 3]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_size": 0}, "max_size"),
        ({"backup_count": 0}, "backup_count"),
    ],
)
def test_invalid_configuration(tmp_path, kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        FilePersistence(tmp_path / "events.jsonl", **kwargs)


@pytest.mark.parametrize(("start_id", "batch"), [(-1, 1), (0, 0), (True, 1)])
def test_invalid_replay_arguments(tmp_path, start_id, batch) -> None:
    store = FilePersistence(tmp_path / "events.jsonl")
    with pytest.raises(ValueError):
        store.replay(start_id=start_id, batch=batch)


def test_serialization_failure_is_store_error(tmp_path) -> None:
    store = FilePersistence(tmp_path / "events.jsonl")
    with pytest.raises(StoreError, match="serialized"):
        store.append(Event("bad", object()))


def test_close_is_idempotent_and_operations_after_close_fail(tmp_path) -> None:
    store = FilePersistence(tmp_path / "events.jsonl")
    store.close()
    store.close()

    with pytest.raises(StoreError, match="closed"):
        store.append(Event("late"))
    with pytest.raises(StoreError, match="closed"):
        list(store.replay())


def test_concurrent_append_keeps_complete_records(tmp_path) -> None:
    store = FilePersistence(tmp_path / "events.jsonl")
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda number: store.append(Event("number", number)), range(100)))

    assert sorted(event.payload for event in store.replay()) == list(range(100))
    store.close()
