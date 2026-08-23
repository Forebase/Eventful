import asyncio

import pytest

from eventful.utilities import async_debounce


def test_construction_and_metadata() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        async_debounce(-0.1)

    @async_debounce(0)
    async def callback(value: int) -> None:
        """Callback documentation."""

    assert callback.__name__ == "callback"
    assert callback.__doc__ == "Callback documentation."
    assert callable(callback.cancel)
    assert callable(callback.flush)


async def test_coalesces_calls_and_delivers_latest_event() -> None:
    delivered = []

    @async_debounce(0.02)
    async def callback(value: int) -> None:
        delivered.append(value)

    await callback(1)
    await callback(2)
    await asyncio.sleep(0.04)
    assert delivered == [2]
    await callback.cancel()


async def test_cancel_discards_pending_call() -> None:
    delivered = []

    @async_debounce(1)
    async def callback(value: int) -> None:
        delivered.append(value)

    await callback(1)
    await callback.cancel()
    await asyncio.sleep(0)
    assert delivered == []


async def test_flush_delivers_pending_call_and_returns_result() -> None:
    delivered = []

    @async_debounce(10)
    async def callback(value: int) -> int:
        delivered.append(value)
        return value * 2

    await callback(3)
    assert await callback.flush() == 6
    assert delivered == [3]
    assert await callback.flush() is None


async def test_background_callback_failure_is_surfaced() -> None:
    @async_debounce(0)
    async def callback(value: int) -> None:
        raise RuntimeError(f"failed: {value}")

    await callback(4)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    with pytest.raises(RuntimeError, match="failed: 4"):
        await callback.flush()


async def test_clean_shutdown_cancels_sleeping_task() -> None:
    @async_debounce(60)
    async def callback() -> None:
        raise AssertionError("must not run")

    await callback()
    await callback.cancel()
    assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
