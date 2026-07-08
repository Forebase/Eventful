"""
Rate limiting utilities for event listeners.
"""

from __future__ import annotations

import time
from typing import Callable, Optional
from threading import Lock


def rate_limit(calls: int, period: float) -> Callable:
    """
    Decorator to rate limit a listener function using token bucket algorithm.

    Parameters
    ----------
    calls : int
        Number of calls allowed per period.
    period : float
        Time period in seconds.

    Returns
    -------
    Callable
        Decorated function with rate limiting.

    Example
    -------
    ```python
    @rate_limit(calls=10, period=60.0)  # 10 calls per minute
    def limited_listener(event):
        # This will be called at most 10 times per minute
        process_event(event)
    ```
    """

    def decorator(func: Callable) -> Callable:
        call_times = []
        lock = Lock()

        def wrapper(event) -> Optional[Any]:
            nonlocal call_times
            current_time = time.time()

            with lock:
                # Remove calls outside the current period
                call_times = [t for t in call_times if current_time - t < period]

                if len(call_times) >= calls:
                    # Rate limit exceeded
                    return None

                call_times.append(current_time)

            return func(event)

        # Preserve original function attributes
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator


class RateLimiter:
    """
    Class-based rate limiter for more complex scenarios.
    """

    def __init__(self, calls: int, period: float):
        """
        Initialize rate limiter.

        Parameters
        ----------
        calls : int
            Number of calls allowed per period.
        period : float
            Time period in seconds.
        """
        self.calls = calls
        self.period = period
        self.call_times = []
        self.lock = Lock()

    def __call__(self, func: Callable) -> Callable:
        """Use as a decorator."""

        def wrapper(event) -> Optional[Any]:
            current_time = time.time()

            with self.lock:
                # Remove calls outside the current period
                self.call_times = [t for t in self.call_times if current_time - t < self.period]

                if len(self.call_times) >= self.calls:
                    return None

                self.call_times.append(current_time)

            return func(event)

        return wrapper

    def acquire(self) -> bool:
        """
        Try to acquire a token.

        Returns
        -------
        bool
            True if token was acquired, False if rate limited.
        """
        current_time = time.time()

        with self.lock:
            self.call_times = [t for t in self.call_times if current_time - t < self.period]

            if len(self.call_times) >= self.calls:
                return False

            self.call_times.append(current_time)
            return True

    @property
    def remaining_calls(self) -> int:
        """Get number of remaining calls in current period."""
        current_time = time.time()

        with self.lock:
            self.call_times = [t for t in self.call_times if current_time - t < self.period]
            return max(0, self.calls - len(self.call_times))

    @property
    def reset_time(self) -> float:
        """Get time when the rate limit will reset."""
        if not self.call_times:
            return time.time()

        current_time = time.time()

        with self.lock:
            self.call_times = [t for t in self.call_times if current_time - t < self.period]
            if not self.call_times:
                return current_time

            oldest_call = min(self.call_times)
            return oldest_call + self.period
