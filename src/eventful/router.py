"""
Topic-based event routing with wildcard support.
"""

from __future__ import annotations

from typing import List, Set

from src.eventful.event import Event
from src.eventful.listener import Listener


class Router:
    """
    Router for matching events to listeners based on topic patterns.

    Supports hierarchical topics with * (single-level) and ** (multi-level) wildcards.
    """

    def __init__(self):
        self._listeners: dict[str, List[Listener]] = {}
        self._wildcard_listeners: List[tuple[str, Listener]] = []

    def add_listener(self, topic: str, listener: Listener) -> None:
        """
        Add a listener for a topic pattern.

        Parameters
        ----------
        topic : str
            Topic pattern (may contain wildcards)
        listener : Listener
            Listener to add
        """
        if '*' in topic or '**' in topic:
            self._wildcard_listeners.append((topic, listener))
        else:
            if topic not in self._listeners:
                self._listeners[topic] = []
            self._listeners[topic].append(listener)

    def remove_listener(self, topic: str, listener: Listener) -> None:
        """
        Remove a listener from a topic pattern.

        Parameters
        ----------
        topic : str
            Topic pattern
        listener : Listener
            Listener to remove
        """
        if '*' in topic or '**' in topic:
            self._wildcard_listeners = [(t, l) for t, l in self._wildcard_listeners
                                        if not (t == topic and l == listener)]
        else:
            if topic in self._listeners:
                self._listeners[topic] = [l for l in self._listeners[topic] if l != listener]
                if not self._listeners[topic]:
                    del self._listeners[topic]

    def get_listeners(self, event: Event) -> List[Listener]:
        """
        Get all listeners that match the given event.

        Parameters
        ----------
        event : Event
            Event to match

        Returns
        -------
        List[Listener]
            List of matching listeners
        """
        listeners = []
        event_type = event.type

        # Exact matches
        if event_type in self._listeners:
            listeners.extend(self._listeners[event_type])

        # Wildcard matches
        for pattern, listener_obj in self._wildcard_listeners:
            if self._matches_pattern(event_type, pattern):
                listeners.append(listener_obj)

        # Filter by listener-specific criteria
        return [l for l in listeners if l.matches(event)]

    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """
        Check if event type matches a wildcard pattern.

        Parameters
        ----------
        event_type : str
            Event type to match
        pattern : str
            Pattern with wildcards

        Returns
        -------
        bool
            True if pattern matches
        """
        if pattern == event_type:
            return True

        pattern_parts = pattern.split('.')
        event_parts = event_type.split('.')

        i = j = 0
        while i < len(pattern_parts) and j < len(event_parts):
            if pattern_parts[i] == '**':
                # Multi-level wildcard - match remaining event parts
                return True
            elif pattern_parts[i] == '*':
                # Single-level wildcard - match exactly one part
                i += 1
                j += 1
            elif pattern_parts[i] == event_parts[j]:
                i += 1
                j += 1
            else:
                return False

        # Both should be exhausted for exact match
        return i == len(pattern_parts) and j == len(event_parts)
