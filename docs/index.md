# Eventful Documentation

Welcome to Eventful, a high-performance event bus system for Python.

### Contents

- [Quick Start](#quick-start)
- [Key Concepts](#key-concepts)
  - [Events](#events)
  - [Listeners](#listeners)
  - [Event Bus](#event-bus)
- [Next Steps](#next-steps)

### Overview

Eventful provides a flexible and extensible event handling system that supports:

- **Sync and Async Listeners**: Handle events synchronously or asynchronously
- **Multiple Transports**: In-memory, Redis, and custom transports
- **Event Persistence**: File-based and database storage
- **Framework Integration**: FastAPI, Starlette adapters
- **Advanced Features**: Rate limiting, debouncing, logging integration

---

## Quick Start

```python
from eventful import Event, emit, listener

@listener("user.created")
def handle_user(event):
    print(f"User: {event.payload}")

emit(Event(type="user.created", payload="Alice"))
````
---

## Key Concepts


### Events

Events are the core building blocks. Each event has:

- type: Hierarchical identifier (e.g., "service.user.created")
- payload: The event data
- metadata: Additional contextual information
- tags: String tags for filtering

### Listeners

Listeners are functions that respond to events. They can be:

- Sync: def listener(event)
- Async: async def listener(event)
- Prioritized: Higher numbers execute first
- Filtered: By topic, tags, or custom logic

### Event Bus

The event bus manages event routing and delivery. Multiple bus implementations are available:

- InMemoryBus: High-performance in-process bus
- RedisBus: Distributed bus using Redis pub/sub

---

## Next Steps

- Quick Start Guide [blocked]
- API Reference [blocked]
- Cookbook Examples [blocked]
- Advanced Topics [blocked]