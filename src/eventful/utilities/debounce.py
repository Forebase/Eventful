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
    # Written this way rather than ``interval < 0`` so NaN is rejected too: NaN
    # is not a meaningful non-negative delay and asyncio's handling varies by
    # Python version.
    if not interval >= 0:
        raise ValueError("interval must be non-negative")

    def decorator(func: Callable) -> Callable:
        task: Optional[asyncio.Task] = None
        pending: Optional[tuple[tuple[Any, ...], dict[str, Any]]] = None
        failure: Optional[BaseException] = None
        foreground_tasks: set[asyncio.Task] = set()
        lock = asyncio.Lock()

        def task_finished(finished: asyncio.Task) -> None:
            """Observe task failures even if the application never calls us again."""
            nonlocal failure, task
            if task is finished:
                task = None
            if finished.cancelled():
                return
            exception = finished.exception()
            if exception is not None and finished not in foreground_tasks:
                failure = exception

        async def stop_task(*, cancel_self: bool = False) -> None:
            nonlocal task
            current, task = task, None
            if current is None:
                return
            if current is asyncio.current_task():
                # A callback may invoke its own wrapper.  It must not await itself;
                # the caller will install the replacement task after this returns.
                if cancel_self:
                    current.cancel()
                return
            if not current.done():
                current.cancel()
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
                await stop_task(cancel_self=True)
                raise_failure()

        async def flush() -> Any:
            nonlocal pending, task
            async with lock:
                raise_failure()
                call, pending = pending, None
                if call is not None:
                    await stop_task()
                    args, kwargs = call
                    loop = asyncio.get_running_loop()
                    running = loop.create_task(func(*args, **kwargs))
                    running.add_done_callback(task_finished)
                    task = running
                else:
                    running = task
                if running is asyncio.current_task():
                    # A callback flushing itself with no newly pending invocation
                    # has nothing to deliver.  Awaiting ``running`` here would make
                    # the task await itself and raise at runtime.
                    return None
                if running is not None:
                    foreground_tasks.add(running)
            if running is None:
                return None
            try:
                return await running
            finally:
                foreground_tasks.discard(running)
                async with lock:
                    if task is running:
                        task = None

        wrapper.cancel = cancel
        wrapper.flush = flush

        return wrapper

    return decorator
