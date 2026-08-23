"""Redis Pub/Sub implementation of Eventful's asynchronous transport contracts.

Events publish to channels derived from their event type. Redis Pub/Sub provides
live, at-most-once fan-out: it has no replay, acknowledgement, or durability. The
transport owns clients it creates, while injected clients remain caller-owned.
redis-py's configured connection retry and Pub/Sub resubscription behavior may
handle transient reconnects. Eventful adds no retry loop: failures left by the
client are surfaced, and publications are never replayed.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from typing import Any

from eventful._optional import require_optional
from eventful.codecs import JsonCodec
from eventful.contracts import Codec
from eventful.event import Event
from eventful.exceptions import CodecError, TransportError


class RedisPublisher:
    """Publish encoded events through a transport-owned Redis client."""

    def __init__(self, transport: RedisTransport) -> None:
        """Bind the endpoint lifecycle to one open transport."""
        self._transport = transport
        self._closed = False

    async def publish(self, event: Event) -> None:
        """Publish once, surfacing any failure not retried by redis-py."""
        if self._closed:
            raise TransportError("Redis publisher is closed")
        self._transport._ensure_open()
        if not isinstance(event, Event):
            raise TypeError("event must be an Event")
        if not event.type:
            raise TransportError("event type must not be empty")
        payload = self._transport.codec.encode(event)
        try:
            await self._transport.client.publish(
                self._transport.channel(event.type), payload
            )
        except (CodecError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise TransportError(
                f"Redis publish failed for event type {event.type!r}"
            ) from exc

    async def close(self) -> None:
        """Close this lightweight endpoint without closing the shared client."""
        self._closed = True


class RedisConsumer:
    """Consume decoded events from one exact Redis Pub/Sub channel."""

    def __init__(self, transport: RedisTransport, topic: str) -> None:
        """Create a lazy subscription for a validated event topic."""
        self._transport = transport
        self._topic = topic
        self._pubsub: Any | None = None
        self._closed = False
        self._consuming = False
        self._lifecycle_lock = asyncio.Lock()

    @property
    def topic(self) -> str:
        """Return the immutable unprefixed event topic."""
        return self._topic

    async def subscribe(self) -> None:
        """Subscribe once, surfacing any failure not recovered by redis-py."""
        await self._subscribe()

    async def consume(self) -> AsyncIterator[Event]:
        """Yield live events, surfacing unrecovered reads and invalid payloads."""
        async with self._lifecycle_lock:
            if self._closed:
                raise TransportError("Redis consumer is closed")
            if self._consuming:
                raise TransportError("Redis consumer already has an active iterator")
            self._consuming = True

        try:
            pubsub = await self._subscribe()
            while not self._closed:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=self._transport.poll_timeout,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if self._closed:
                        break
                    raise TransportError(
                        f"Redis consume failed for topic {self.topic!r}"
                    ) from exc
                if message is None:
                    continue
                if message.get("type") not in {"message", b"message"}:
                    continue
                data = message.get("data")
                if not isinstance(data, bytes):
                    raise TransportError("Redis event payload must be bytes")
                try:
                    event = self._transport.codec.decode(data)
                except CodecError as exc:
                    raise TransportError(
                        f"Redis event payload is invalid for topic {self.topic!r}"
                    ) from exc
                if event.type != self.topic:
                    raise TransportError(
                        "Redis event type does not match its subscription topic"
                    )
                yield event
        finally:
            async with self._lifecycle_lock:
                self._consuming = False
            active_failure = sys.exception()
            try:
                await self.close()
            except TransportError:
                # Cleanup must not replace cancellation, malformed-message, or
                # connection errors already escaping the iterator. GeneratorExit
                # denotes an explicit/normal iterator close, so its cleanup error
                # remains observable to the caller.
                if active_failure is None or isinstance(active_failure, GeneratorExit):
                    raise

    async def close(self) -> None:
        """Unsubscribe and close the Pub/Sub resource idempotently."""
        async with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            pubsub, self._pubsub = self._pubsub, None
        if pubsub is not None:
            failure: BaseException | None = None
            try:
                await pubsub.unsubscribe(self._transport.channel(self.topic))
            except Exception as exc:
                failure = exc
            try:
                await pubsub.aclose()
            except Exception as exc:
                failure = failure or exc
            if failure is not None:
                self._transport._discard_consumer(self)
                raise TransportError(
                    f"Redis consumer close failed for topic {self.topic!r}"
                ) from failure
        self._transport._discard_consumer(self)

    async def _subscribe(self) -> Any:
        """Create and initialize the underlying Pub/Sub subscription once."""
        self._transport._ensure_open()
        async with self._lifecycle_lock:
            if self._closed:
                raise TransportError("Redis consumer is closed")
            if self._pubsub is not None:
                return self._pubsub
            pubsub = self._transport.client.pubsub()
            try:
                await pubsub.subscribe(self._transport.channel(self.topic))
            except BaseException as exc:
                # Cancellation is deliberately included: a connection attempt may
                # be cancelled while redis-py is reconnecting, but its Pub/Sub
                # object must not retain a duplicate server-side subscription.
                try:
                    await asyncio.shield(pubsub.aclose())
                except BaseException as cleanup_exc:
                    # In particular, task cancellation must remain cancellation
                    # even when a broken connection also makes cleanup fail.
                    exc.add_note(
                        "Redis subscription cleanup also failed: "
                        f"{cleanup_exc!r}"
                    )
                if isinstance(exc, asyncio.CancelledError):
                    raise exc
                raise TransportError(
                    f"Redis subscribe failed for topic {self.topic!r}"
                ) from exc
            self._pubsub = pubsub
            return pubsub


class RedisTransport:
    """Own Redis Pub/Sub endpoints and their shared asynchronous client."""

    def __init__(
        self,
        url: str,
        *,
        codec: Codec | None = None,
        channel_prefix: str = "eventful:",
        poll_timeout: float = 1.0,
        client: Any | None = None,
        **redis_options: Any,
    ) -> None:
        """Configure lazy endpoints and optionally create an owned Redis client."""
        if not url:
            raise ValueError("url must not be empty")
        if poll_timeout <= 0:
            raise ValueError("poll_timeout must be greater than zero")
        redis_asyncio = require_optional("RedisTransport", "redis", "redis.asyncio")
        self.url = url
        self.codec = codec or JsonCodec()
        self.channel_prefix = channel_prefix
        self.poll_timeout = poll_timeout
        self._owns_client = client is None
        self.client = client or redis_asyncio.Redis.from_url(
            url, decode_responses=False, **redis_options
        )
        self._publisher = RedisPublisher(self)
        self._consumers: set[RedisConsumer] = set()
        self._closed = False
        self._close_lock = asyncio.Lock()

    def publisher(self) -> RedisPublisher:
        """Return the transport's single lightweight publishing endpoint."""
        self._ensure_open()
        return self._publisher

    def consumer(self, topic: str) -> RedisConsumer:
        """Create an independently owned exact-topic consumer."""
        self._ensure_open()
        if not topic:
            raise ValueError("topic must not be empty")
        consumer = RedisConsumer(self, topic)
        self._consumers.add(consumer)
        return consumer

    def channel(self, topic: str) -> str:
        """Map an Eventful topic to its Redis channel name."""
        return f"{self.channel_prefix}{topic}"

    async def close(self) -> None:
        """Close all endpoints and the owned client idempotently."""
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
            consumers = list(self._consumers)
        failures = await asyncio.gather(
            *(consumer.close() for consumer in consumers), return_exceptions=True
        )
        await self._publisher.close()
        if self._owns_client:
            try:
                await self.client.aclose()
            except Exception as exc:
                raise TransportError("Redis client close failed") from exc
        for failure in failures:
            if isinstance(failure, BaseException):
                raise TransportError("Redis consumer shutdown failed") from failure

    async def __aenter__(self) -> RedisTransport:
        """Return the open transport for asynchronous context management."""
        self._ensure_open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Close owned resources when leaving an asynchronous context."""
        await self.close()

    def _discard_consumer(self, consumer: RedisConsumer) -> None:
        """Forget a closed consumer without requiring asynchronous locking."""
        self._consumers.discard(consumer)

    def _ensure_open(self) -> None:
        """Reject endpoint creation and operations after shutdown."""
        if self._closed:
            raise TransportError("Redis transport is closed")


__all__ = ["RedisConsumer", "RedisPublisher", "RedisTransport"]
