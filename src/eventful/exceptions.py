"""Shared exception hierarchy for Eventful."""
from __future__ import annotations
from ._optional import OptionalDependencyError

class EventfulError(Exception):
    """Base class for Eventful errors."""
class ConfigurationError(EventfulError):
    """Invalid configuration or configuration source failure."""
class ContractError(EventfulError):
    """A component violated a documented Eventful contract."""
class CodecError(EventfulError):
    """Event encoding or decoding failed."""
class StoreError(EventfulError):
    """Durable event storage failed."""
