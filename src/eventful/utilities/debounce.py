"""
Debouncing utilities for event listeners.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Optional, Any
from threading import Lock, Timer
from concurrent.futures import ThreadPoolExecutor

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
        executor = ThreadPoolExecutor(max_workers=1)

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

async def async_debounce(interval: float) -> Callable:
    """
    Async version of debounce decorator.

    Parameters
    ----------
    interval : float
        Time interval in seconds.

    Returns
    -------
    Callable
        Decorated async function.
    """
    def decorator(func: Callable) -> Callable:
        last_call_time = 0.0
        task = None
        lock = asyncio.Lock()

        async def wrapper(event) -> None:
            nonlocal last_call_time, task

            current_time = time.time()
            last_call_time = current_time

            async with lock:
                # Cancel previous task
                if task and not task.done():
                    task.cancel()

                # Schedule new task
                async def delayed_call():
                    await asyncio.sleep(interval)
                    # Check if we're still the most recent call
                    nonlocal last_call_time
                    if time.time() - last_call_time >= interval:
                        await func(event)

                task = asyncio.create_task(delayed_call())

        return wrapper

    return decorator
