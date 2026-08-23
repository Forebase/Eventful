"""Static assignments proving reference implementations satisfy protocols."""

from eventful.bus import EventBus
from eventful.codecs import JsonCodec
from eventful.contracts import Codec, EventBusContract, EventStore
from eventful.stores import InMemoryEventStore

bus: EventBusContract = EventBus()
codec: Codec = JsonCodec()
store: EventStore = InMemoryEventStore()
