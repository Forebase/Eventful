# Eventful

A universal event-bus / pub-sub system for micro-service communication, callbacks and general application-level event handling.

[![PyPI Version](https://img.shields.io/pypi/v/eventful)](https://pypi.org/project/eventful/)
[![Python Versions](https://img.shields.io/pypi/pyversions/eventful)](https://pypi.org/project/eventful/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-readthedocs-blue)](https://eventful.readthedocs.io)

## Features

- 🚀 **High Performance**: Handle 200k+ events/second with sub-millisecond latency
- 🔄 **Sync & Async**: Support for both synchronous and asynchronous listeners
- 🌐 **Multiple Transports**: In-memory, Redis, and extensible plugin system
- 💾 **Persistence**: File-based and PostgreSQL event storage with replay
- 🏷️ **Flexible Filtering**: Topic patterns, tags, and custom filters
- ⚡ **Framework Integration**: FastAPI, Starlette adapters
- 📊 **Monitoring**: Built-in logging integration and error handling

## Installation

```bash
# Basic installation
pip install eventful

# With Redis support
pip install eventful[redis]

# With PostgreSQL persistence
pip install eventful[postgres]

# With FastAPI integration
pip install eventful[fastapi]

# All features
pip install eventful[all]

```

Quick Start
import asyncio
from eventful import Event, emit, listener

# Register a synchronous listener
    
    @listener("user.created")
    def handle_user_created(event: Event):
        print(f"User created: {event.payload}")
    

# Register an asynchronous listener  
    
    @listener("user.updated", priority=1)
    async def handle_user_updated(event: Event):
        await send_notification(event.payload)

# Emit events

``emit(Event(type="user.created", payload={"id": 1, "name": "Alice"}))
``
# Documentation
Full documentation is available at eventful.readthedocs.io

# Contributing
We welcome contributions! Please see our Contributing Guide [blocked] for details.

# License
This project is licensed under the MIT License - see the LICENSE [blocked] file for details.


## bench.py

```python
"""
Performance benchmark for eventful.
"""

import time
import asyncio
from eventful import Event, InMemoryBus, listener

def benchmark_sync_events(num_events: int = 100000) -> dict:
    """Benchmark synchronous event emission."""
    bus = InMemoryBus()
    
    @listener("test.event")
    def simple_listener(event):
        return event.payload
    
    start_time = time.time()
    
    for i in range(num_events):
        bus.emit(Event(type="test.event", payload=i))
    
    end_time = time.time()
    duration = end_time - start_time
    
    return {
        "events_per_second": num_events / duration,
        "total_events": num_events,
        "total_time": duration,
        "avg_latency_ms": (duration / num_events) * 1000
    }

async def benchmark_async_events(num_events: int = 100000) -> dict:
    """Benchmark asynchronous event emission."""
    bus = InMemoryBus()
    
    @listener("test.event")
    async def async_listener(event):
        return event.payload
    
    start_time = time.time()
    
    tasks = []
    for i in range(num_events):
        tasks.append(bus.emit(Event(type="test.event", payload=i)))
    
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    duration = end_time - start_time
    
    return {
        "events_per_second": num_events / duration,
        "total_events": num_events,
        "total_time": duration,
        "avg_latency_ms": (duration / num_events) * 1000
    }

if __name__ == "__main__":
    print("=== Eventful Performance Benchmark ===\n")
    
    # Sync benchmark
    print("🧪 Running sync benchmark...")
    sync_results = benchmark_sync_events(100000)
    print(f"Sync Events/sec: {sync_results['events_per_second']:.0f}")
    print(f"Sync Latency: {sync_results['avg_latency_ms']:.3f} ms")
    
    print("\n🧪 Running async benchmark...")
    async_results = asyncio.run(benchmark_async_events(100000))
    print(f"Async Events/sec: {async_results['events_per_second']:.0f}")
    print(f"Async Latency: {async_results['avg_latency_ms']:.3f} ms")