"""Static assignments proving reference implementations satisfy protocols."""

from eventful.bus import EventBus
from eventful.codecs import JsonCodec
from eventful.contracts import (
    Codec,
    Consumer,
    EventBusContract,
    EventStore,
    Publisher,
    Transport,
)
from eventful.stores import InMemoryEventStore
from eventful.transports.redis import RedisTransport

bus: EventBusContract = EventBus()
codec: Codec = JsonCodec()
store: EventStore = InMemoryEventStore()
transport: Transport = RedisTransport("redis://localhost:6379")
publisher: Publisher = transport.publisher()
consumer: Consumer = transport.consumer("typing.sample")
