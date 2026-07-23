"""
Event dispatch ordering and prioritization.
"""

from __future__ import annotations

from typing import List

from .listener import Listener


class Dispatcher:
    """
    Handles listener dispatch order based on priority and registration order.
    """

    def __init__(self, enable_priorities: bool = True, propagation_enabled: bool = True):
        """
        Initialize dispatcher.

        Parameters
        ----------
        enable_priorities : bool
            Whether to use priority-based ordering
        propagation_enabled : bool
            Whether propagation control is enabled
        """
        self.enable_priorities = enable_priorities
        self.propagation_enabled = propagation_enabled

    def dispatch_order(self, listeners: List[Listener]) -> List[Listener]:
        """
        Get listeners in the correct dispatch order.

        Parameters
        ----------
        listeners : List[Listener]
            Input listeners

        Returns
        -------
        List[Listener]
            Listeners in dispatch order
        """
        if self.enable_priorities:
            # Sort by priority (highest first), then by registration order (FIFO)
            sorted_listeners = sorted(listeners, key=lambda l: l.config.priority, reverse=True)
        else:
            # Pure FIFO (maintain original order)
            sorted_listeners = listeners

        return sorted_listeners
