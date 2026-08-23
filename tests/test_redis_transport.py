"""Unit and service-backed tests for the Redis Pub/Sub transport."""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from eventful import Event
from eventful.contracts import Consumer, Publisher, Transport
from eventful.exceptions import TransportError
from eventful.transports.redis import RedisTransport


class RestartableRedis:
    """Own a disposable Redis process for a genuine restart boundary test."""

    def __init__(self, executable: str, directory: Path, port: int) -> None:
        self.executable = executable
        self.directory = directory
        self.port = port
        self.process: subprocess.Popen[bytes] | None = None

    @property
    def url(self) -> str:
        """Return this isolated server's connection URL."""
        return f"redis://127.0.0.1:{self.port}/0"

    def start(self) -> None:
        """Start Redis and wait until its TCP listener is ready."""
        self.process = subprocess.Popen(
            [
                self.executable,
                "--port",
                str(self.port),
                "--dir",
                str(self.directory),
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with socket.socket() as connection:
                if connection.connect_ex(("127.0.0.1", self.port)) == 0:
                    return
            time.sleep(0.01)
        raise RuntimeError("disposable Redis did not start")

    def stop(self) -> None:
        """Stop Redis without persistence and wait for process collection."""
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=3)
            self.process = None


@pytest.fixture
def restartable_redis(tmp_path: Path) -> Iterator[RestartableRedis]:
    """Provide a real restartable server when redis-server is installed."""
    executable = shutil.which("redis-server")
    if executable is None:
        pytest.skip("redis-server executable is not installed")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server = RestartableRedis(executable, tmp_path, port)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def redis_service_url() -> str:
    """Return the explicitly configured service URL or skip integration tests."""
    url = os.getenv("EVENTFUL_REDIS_URL")
    if url is None:
        pytest.skip("EVENTFUL_REDIS_URL is not configured")
    return url


def redis_service_transport(**options: Any) -> RedisTransport:
    """Create an isolated transport against the configured Redis service."""
    return RedisTransport(
        redis_service_url(),
        channel_prefix=f"eventful-tests:{os.getpid()}:{uuid.uuid4().hex}:",
        poll_timeout=0.02,
        **options,
    )


class FakePubSub:
    """Model the redis-py Pub/Sub methods used by the transport."""

    def __init__(self, client: FakeRedis) -> None:
        """Create an unsubscribed queue registered with a fake client."""
        self.client = client
        self.channels: set[str] = set()
        self.messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        """Subscribe this fake resource to one channel."""
        self.channels.add(channel)
        self.client.subscriptions.add(self)

    async def unsubscribe(self, channel: str) -> None:
        """Remove one fake channel subscription."""
        self.channels.discard(channel)

    async def get_message(
        self, *, ignore_subscribe_messages: bool, timeout: float
    ) -> dict[str, Any] | None:
        """Return the next queued message or `None` at the poll timeout."""
        del ignore_subscribe_messages
        try:
            return await asyncio.wait_for(self.messages.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def aclose(self) -> None:
        """Close and unregister this fake Pub/Sub resource."""
        self.closed = True
        self.client.subscriptions.discard(self)


class FakeRedis:
    """Route published bytes to matching in-memory fake subscriptions."""

    def __init__(self) -> None:
        """Create an open fake client without subscriptions."""
        self.subscriptions: set[FakePubSub] = set()
        self.closed = False
        self.publish_error: Exception | None = None

    def pubsub(self) -> FakePubSub:
        """Create a fake Pub/Sub resource."""
        return FakePubSub(self)

    async def publish(self, channel: str, payload: bytes) -> int:
        """Fan out bytes to current exact-channel subscribers."""
        if self.publish_error is not None:
            raise self.publish_error
        delivered = 0
        for subscription in tuple(self.subscriptions):
            if channel in subscription.channels:
                await subscription.messages.put({"type": "message", "data": payload})
                delivered += 1
        return delivered

    async def aclose(self) -> None:
        """Mark the fake client closed."""
        self.closed = True


async def next_event(consumer: Consumer) -> Event:
    """Read one event and close the asynchronous iterator deterministically."""
    iterator = consumer.consume()
    try:
        return await anext(iterator)
    finally:
        await iterator.aclose()


def make_transport(client: FakeRedis | None = None) -> tuple[RedisTransport, FakeRedis]:
    """Create a fast injected-client transport for unit tests."""
    fake = client or FakeRedis()
    return (
        RedisTransport(
            "redis://unused",
            client=fake,
            channel_prefix="tests:",
            poll_timeout=0.01,
        ),
        fake,
    )


def test_redis_endpoints_satisfy_runtime_contracts() -> None:
    """Expose the refined transport capabilities at runtime."""
    transport, _ = make_transport()

    assert isinstance(transport, Transport)
    assert isinstance(transport.publisher(), Publisher)
    assert isinstance(transport.consumer("sample"), Consumer)


@pytest.mark.asyncio
async def test_publish_consume_round_trip_and_prefix_isolation() -> None:
    """Round-trip one event only to its exact prefixed topic."""
    transport, _ = make_transport()
    matching = transport.consumer("user.created")
    other = transport.consumer("user.deleted")
    pending = asyncio.create_task(next_event(matching))
    await asyncio.sleep(0)

    event = Event("user.created", {"id": 7}, tags={"audit"})
    await transport.publisher().publish(event)

    assert await asyncio.wait_for(pending, timeout=1) == event
    assert other._pubsub is None
    await other.close()
    await transport.close()


@pytest.mark.asyncio
async def test_consumer_rejects_malformed_and_mismatched_messages() -> None:
    """Stop consumption rather than yielding corrupt broker data."""
    transport, fake = make_transport()
    consumer = transport.consumer("expected")
    iterator = consumer.consume()
    pending = asyncio.create_task(anext(iterator))
    await asyncio.sleep(0)
    pubsub = next(iter(fake.subscriptions))
    await pubsub.messages.put({"type": "message", "data": b"not-json"})

    with pytest.raises(TransportError, match="invalid"):
        await pending
    await iterator.aclose()

    second = transport.consumer("expected")
    second_iterator = second.consume()
    pending = asyncio.create_task(anext(second_iterator))
    await asyncio.sleep(0)
    second_pubsub = next(iter(fake.subscriptions))
    await second_pubsub.messages.put(
        {"type": "message", "data": transport.codec.encode(Event("different"))}
    )
    with pytest.raises(TransportError, match="does not match"):
        await pending
    await second_iterator.aclose()
    await transport.close()


@pytest.mark.asyncio
async def test_publish_errors_are_translated_with_cause() -> None:
    """Preserve client failures behind the transport exception hierarchy."""
    fake = FakeRedis()
    fake.publish_error = ConnectionError("offline")
    transport, _ = make_transport(fake)

    with pytest.raises(TransportError, match="publish failed") as raised:
        await transport.publisher().publish(Event("sample"))

    assert isinstance(raised.value.__cause__, ConnectionError)
    await transport.close()


@pytest.mark.asyncio
async def test_lifecycle_is_idempotent_and_respects_injected_ownership() -> None:
    """Close subscriptions but leave a caller-owned Redis client open."""
    transport, fake = make_transport()
    consumer = transport.consumer("sample")
    await consumer.subscribe()
    await consumer.subscribe()
    assert len(fake.subscriptions) == 1

    await transport.close()
    await transport.close()

    assert fake.closed is False
    assert not fake.subscriptions
    with pytest.raises(TransportError, match="closed"):
        transport.consumer("later")


@pytest.mark.asyncio
async def test_publisher_close_does_not_close_shared_transport() -> None:
    """Keep endpoint and shared-client lifecycle responsibilities separate."""
    transport, _ = make_transport()
    publisher = transport.publisher()
    await publisher.close()

    with pytest.raises(TransportError, match="publisher is closed"):
        await publisher.publish(Event("sample"))
    assert transport.consumer("sample").topic == "sample"
    await transport.close()


@pytest.mark.asyncio
async def test_consumer_cancellation_cleans_up_subscription() -> None:
    """Preserve cancellation while closing the consumer's Pub/Sub resource."""
    transport, fake = make_transport()
    consumer = transport.consumer("sample")
    await consumer.subscribe()
    iterator = consumer.consume()
    pending = asyncio.create_task(anext(iterator))
    await asyncio.sleep(0)

    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending

    assert not fake.subscriptions
    with pytest.raises(TransportError, match="consumer is closed"):
        await anext(consumer.consume())
    await transport.close()


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_pubsub_round_trip() -> None:
    """Validate serialization, subscription, publication, and shutdown end to end."""
    async with redis_service_transport() as transport:
        consumer = transport.consumer("integration.created")
        await consumer.subscribe()
        pending = asyncio.create_task(next_event(consumer))
        event = Event("integration.created", {"working": True})

        await transport.publisher().publish(event)

        assert await asyncio.wait_for(pending, timeout=3) == event


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_connection_loss_during_publish_is_surfaced() -> None:
    """Surface an unconfigured publish retry without implying safe replay."""
    transport = redis_service_transport()
    publisher = transport.publisher()
    original = transport.client.publish

    async def lose_connection(channel: str, payload: bytes) -> int:
        del channel, payload
        await transport.client.connection_pool.disconnect()
        raise ConnectionError("forced publisher connection loss")

    transport.client.publish = lose_connection
    with pytest.raises(TransportError, match="publish failed") as raised:
        await publisher.publish(Event("publish.loss"))
    assert isinstance(raised.value.__cause__, ConnectionError)

    transport.client.publish = original
    await publisher.publish(Event("publish.recovered"))
    await transport.close()


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_subscription_reconnects_after_connection_restart() -> None:
    """Restore a subscription after its server connection is torn down."""
    async with redis_service_transport() as transport:
        consumer = transport.consumer("restart")
        await consumer.subscribe()
        assert consumer._pubsub is not None
        await consumer._pubsub.connection.disconnect()

        pending = asyncio.create_task(next_event(consumer))
        # A poll drives redis-py's reconnect and resubscription. Events in the gap
        # are intentionally not counted because Pub/Sub remains at-most-once.
        await asyncio.sleep(0.1)
        expected = Event("restart", {"after": True})
        await transport.publisher().publish(expected)
        assert await asyncio.wait_for(pending, timeout=3) == expected


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_consumer_recovers_after_server_restart(
    restartable_redis: RestartableRedis,
) -> None:
    """Surface the broken read, then recover with a fresh post-restart consumer."""
    async with RedisTransport(
        restartable_redis.url,
        channel_prefix=f"restart:{uuid.uuid4().hex}:",
        poll_timeout=0.02,
    ) as transport:
        consumer = transport.consumer("server")
        await consumer.subscribe()
        restartable_redis.stop()
        failed = asyncio.create_task(next_event(consumer))
        with pytest.raises(TransportError, match="consume failed"):
            await asyncio.wait_for(failed, timeout=3)
        restartable_redis.start()
        replacement = transport.consumer("server")
        await replacement.subscribe()
        pending = asyncio.create_task(next_event(replacement))
        expected = Event("server", {"after_restart": True})
        await transport.publisher().publish(expected)
        assert await asyncio.wait_for(pending, timeout=3) == expected


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_cancellation_while_reconnecting_cleans_up() -> None:
    """Propagate cancellation and leave no consumer after a disconnected poll."""
    async with redis_service_transport() as transport:
        consumer = transport.consumer("cancel.reconnect")
        await consumer.subscribe()
        assert consumer._pubsub is not None
        await consumer._pubsub.connection.disconnect()
        iterator = consumer.consume()
        pending = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert consumer not in transport._consumers


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_duplicate_subscription_cleanup() -> None:
    """Keep one server subscription and remove it on idempotent close."""
    async with redis_service_transport() as transport:
        consumer = transport.consumer("duplicate")
        await asyncio.gather(consumer.subscribe(), consumer.subscribe())
        channel = transport.channel("duplicate")
        assert await transport.client.pubsub_numsub(channel) == [(channel.encode(), 1)]
        await consumer.close()
        await consumer.close()
        assert await transport.client.pubsub_numsub(channel) == [(channel.encode(), 0)]


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_malformed_message_is_surfaced() -> None:
    """Reject malformed service data and close the affected subscription."""
    async with redis_service_transport() as transport:
        consumer = transport.consumer("malformed")
        await consumer.subscribe()
        iterator = consumer.consume()
        pending = asyncio.create_task(anext(iterator))
        await transport.client.publish(transport.channel("malformed"), b"not-json")
        with pytest.raises(TransportError, match="invalid"):
            await asyncio.wait_for(pending, timeout=3)
        assert consumer not in transport._consumers


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_sustained_concurrent_publishing() -> None:
    """Deliver a sustained concurrent burst once subscription readiness is known."""
    async with redis_service_transport() as transport:
        consumer = transport.consumer("burst")
        await consumer.subscribe()
        total = 250

        async def receive() -> set[int]:
            received: set[int] = set()
            async for event in consumer.consume():
                received.add(event.payload["sequence"])
                if len(received) == total:
                    return received
            return received

        pending = asyncio.create_task(receive())
        queue = asyncio.Queue[int]()
        for index in range(total):
            queue.put_nowait(index)

        async def publish_worker() -> None:
            while not queue.empty():
                index = queue.get_nowait()
                await transport.publisher().publish(
                    Event("burst", {"sequence": index})
                )

        # Sustained concurrency is intentionally bounded: redis-py's default
        # connection pool rejects an unbounded task fan-out at its connection cap.
        await asyncio.gather(*(publish_worker() for _ in range(10)))
        assert await asyncio.wait_for(pending, timeout=10) == set(range(total))


@pytest.mark.redis_integration
@pytest.mark.asyncio
async def test_real_redis_shutdown_is_deterministic() -> None:
    """Bound shutdown with active consumers and reject all later operations."""
    transport = redis_service_transport()
    consumers = [transport.consumer(f"shutdown.{index}") for index in range(20)]
    await asyncio.gather(*(consumer.subscribe() for consumer in consumers))
    async with asyncio.timeout(3):
        await transport.close()
        await transport.close()
    assert not transport._consumers
    assert all(consumer._closed for consumer in consumers)
    with pytest.raises(TransportError, match="closed"):
        await transport.publisher().publish(Event("shutdown"))
