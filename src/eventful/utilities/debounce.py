"""
Debouncing utilities for event listeners.
"""

from __future__ import annotations

import asyncio
from functools import wraps
import time
from typing import Callable, Optional, Any
from threading import Lock, Timer

def debounce(interval: float) -> Callable:
    """
    Decorator to debounce a listener function.

    Only calls the function after the specified interval of inactivity.

    Parameters
    ----------
    interval : float
        Time interval in seconds.

    Returns
    -------
    Callable
        Decorated function with debouncing.

    Example
    -------
    ```python
    @debounce(interval=0.5)  # Wait 500ms after last call
    def debounced_listener(event):
        # This will only be called if no events arrive for 500ms
        process_events([event])
    ```
    """
    def decorator(func: Callable) -> Callable:
        last_call_time = 0.0
        timer = None
        lock = Lock()

        def wrapper(event) -> None:
            nonlocal last_call_time, timer

            current_time = time.time()
            last_call_time = current_time

            with lock:
                # Cancel previous timer
                if timer:
                    timer.cancel()

                # Schedule new timer
                def delayed_call():
                    # Check if we're still the most recent call
                    nonlocal last_call_time
                    if time.time() - last_call_time >= interval:
                        func(event)

                timer = Timer(interval, delayed_call)
                timer.start()

        # Preserve original function attributes
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator

class Debouncer:
    """
    Class-based debouncer for more complex scenarios.
    """

    def __init__(self, interval: float):
        """
        Initialize debouncer.

        Parameters
        ----------
        interval : float
            Time interval in seconds.
        """
        self.interval = interval
        self.last_call_time = 0.0
        self.timer = None
        self.lock = Lock()
        self.pending_event = None

    def __call__(self, func: Callable) -> Callable:
        """Use as a decorator."""
        def wrapper(event) -> None:
            self.trigger(event, func)

        return wrapper

    def trigger(self, event: Any, callback: Optional[Callable] = None) -> None:
        """
        Trigger the debouncer with an event.

        Parameters
        ----------
        event : Any
            Event to process.
        callback : Callable | None, optional
            Callback function. If None, uses the function provided to __call__.
        """
        current_time = time.time()
        self.pending_event = event

        with self.lock:
            self.last_call_time = current_time

            # Cancel previous timer
            if self.timer:
                self.timer.cancel()

            # Schedule new timer
            def delayed_call():
                nonlocal current_time
                # Check if we're still the most recent call
                if time.time() - self.last_call_time >= self.interval:
                    if callback and self.pending_event:
                        callback(self.pending_event)
                    self.pending_event = None

            self.timer = Timer(self.interval, delayed_call)
            self.timer.start()

    def cancel(self) -> None:
        """Cancel any pending debounced call."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.pending_event = None

    def flush(self) -> Any:
        """Immediately execute any pending call and return the pending event."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None

            pending = self.pending_event
            self.pending_event = None
            return pending

def async_debounce(interval: float) -> Callable:
    """
    Debounce an async callback without blocking its caller.

    Calls to the wrapper replace pending calls and return after the replacement has
    been scheduled.  ``await wrapper.flush()`` immediately delivers the latest
    pending call (or waits for a callback already in progress), while
    ``await wrapper.cancel()`` discards pending work (or cancels work in progress).
    Both lifecycle methods wait for the background task to finish, making them safe
    to use during event-loop shutdown.

    Callback exceptions are retrieved from the background task to avoid unobserved
    task warnings.  They are re-raised by the next wrapper, ``cancel``, or ``flush``
    call.  An exception raised by a callback invoked directly by ``flush`` is raised
    by ``flush`` itself.

    Parameters
    ----------
    interval : float
        Time interval in seconds.

    Returns
    -------
    Callable
        Decorated async function.
    """
    if interval < 0:
        raise ValueError("interval must be non-negative")

    def decorator(func: Callable) -> Callable:
        task: Optional[asyncio.Task] = None
        pending: Optional[tuple[tuple[Any, ...], dict[str, Any]]] = None
        failure: Optional[BaseException] = None
        lock = asyncio.Lock()

        def task_finished(finished: asyncio.Task) -> None:
            """Observe task failures even if the application never calls us again."""
            nonlocal failure
            if finished.cancelled():
                return
            exception = finished.exception()
            if exception is not None:
                failure = exception

        async def stop_task() -> None:
            nonlocal task
            current, task = task, None
            if current is not None and not current.done():
                current.cancel()
            if current is not None:
                await asyncio.gather(current, return_exceptions=True)
                await asyncio.sleep(0)

        def raise_failure() -> None:
            nonlocal failure
            if failure is not None:
                exception, failure = failure, None
                raise exception

        async def delayed_call(deadline: float) -> None:
            nonlocal pending
            loop = asyncio.get_running_loop()
            await asyncio.sleep(max(0.0, deadline - loop.time()))
            async with lock:
                call, pending = pending, None
            if call is not None:
                args, kwargs = call
                await func(*args, **kwargs)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> None:
            nonlocal task, pending
            async with lock:
                raise_failure()
                await stop_task()
                raise_failure()
                pending = (args, kwargs)
                loop = asyncio.get_running_loop()
                task = loop.create_task(delayed_call(loop.time() + interval))
                task.add_done_callback(task_finished)

        async def cancel() -> None:
            nonlocal pending
            async with lock:
                pending = None
                await stop_task()
                raise_failure()

        async def flush() -> Any:
            nonlocal pending
            async with lock:
                raise_failure()
                call, pending = pending, None
                if call is not None:
                    await stop_task()
                    running = None
                else:
                    running = task
            if running is not None:
                await asyncio.gather(running, return_exceptions=True)
                # Let the registered observer record the exception before it is
                # surfaced below (``gather`` may have received an already-done task).
                await asyncio.sleep(0)
                async with lock:
                    raise_failure()
                return None
            if call is None:
                return None
            args, kwargs = call
            return await func(*args, **kwargs)

        wrapper.cancel = cancel
        wrapper.flush = flush

        return wrapper

    return decorator
