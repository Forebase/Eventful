"""Static assignments proving reference implementations satisfy protocols."""

from eventful.bus import EventBus
from eventful.codecs import JsonCodec
from eventful.contracts import (
    Codec,
    ConfigurationSource,
    Consumer,
    EventBusContract,
    EventStore,
    ObservabilityProvider,
    Publisher,
    SchemaRegistry,
    Transport,
)
from eventful.stores import InMemoryEventStore
from eventful.persistence import PostgresPersistence
from eventful.configuration import MappingSource
from eventful.observability import InMemoryObservabilityProvider
from eventful.schemas import InMemorySchemaRegistry
from eventful.transports.redis import RedisTransport

bus: EventBusContract = EventBus()
codec: Codec = JsonCodec()
store: EventStore = InMemoryEventStore()
transport: Transport = RedisTransport("redis://localhost:6379")
publisher: Publisher = transport.publisher()
consumer: Consumer = transport.consumer("typing.sample")
postgres_store: EventStore = PostgresPersistence("postgresql://localhost/eventful")
configuration_source: ConfigurationSource = MappingSource({})
schema_registry: SchemaRegistry = InMemorySchemaRegistry()
observability_provider: ObservabilityProvider = InMemoryObservabilityProvider()
