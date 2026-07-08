"""
Propagation control for events.
"""

from __future__ import annotations


class StopPropagation(Exception):
    """
    Sentinel exception to stop event propagation.

    Can be raised by listeners to stop further propagation.
    """
    pass


def stop_propagation() -> None:
    """
    Utility function to stop event propagation.

    Raises
    ------
    StopPropagation
        Always raises StopPropagation exception
    """
    raise StopPropagation()
