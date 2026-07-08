"""
Basic example demonstrating eventful usage.
"""

import asyncio
from eventful import Event, emit, listener, bus


# Basic synchronous listener
@listener("user.created")
def handle_user_created(event: Event):
    print(f"📝 User created: {event.payload}")


# Listener with priority and tags
@listener("user.*", priority=10, tags={"important"})
def high_priority_handler(event: Event):
    print(f"🚀 High priority: {event.type}")


# Asynchronous listener
@listener("email.sent")
async def handle_email_sent(event: Event):
    await asyncio.sleep(0.1)  # Simulate async work
    print(f"📧 Email sent: {event.payload}")


# One-time listener
@listener("system.startup", once=True)
def startup_handler(event: Event):
    print("🔌 System started!")


def main():
    # Emit various events
    emit(Event(type="system.startup"))
    emit(Event(type="user.created", payload="Alice"))
    emit(Event(type="user.updated", payload="Bob", tags={"important"}))
    emit(Event(type="email.sent", payload="welcome@example.com"))

    # Emit event with custom metadata
    event = Event(
        type="payment.processed",
        payload={"amount": 100, "currency": "USD"},
        metadata={"source": "api", "version": "1.0"},
        tags={"finance", "important"}
    )
    emit(event)


async def async_main():
    print("\n=== Async Version ===")

    # Use the bus instance directly with the async method
    await bus.aemit(Event(type="user.created", payload="Alice"))

    # Also use async emit for the other events
    await bus.aemit(Event(type="user.updated", payload="Alice"))
    await bus.aemit(Event(type="email.sent", payload="welcome@example.com"))

if __name__ == "__main__":
    print("=== Eventful Basic Example ===\n")
    main()

    print("\n=== Async Version ===")
    #asyncio.run(async_main())
