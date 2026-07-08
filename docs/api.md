# API Reference

## Core Classes

### Event

The main event class that represents an event in the system.

```python
from typing import Any
from dataclasses import dataclass

@dataclass
class Event:
    type: str                    # Hierarchical event type
    metadata: dict[str, Any]     # Additional metadata
    tags: set[str]              # Filtering tags
    payload: Any = None          # Event data
````

#### Methods:

- **stop_propagation()**: _Stop further propagation to remaining listeners_
- **propagation_stopped**: _Property indicating if propagation was stopped_

### EventBus
Base class for all event bus implementations.

#### Methods:

 - **register(topic, listener, priority=0, tags=(), filter_fn=None, once=False)**: _Register a listener_
 - **unregister(topic, listener)**: _Unregister a listener_
 - **emit(event, async_=None)**: _Emit an event_
 - **set_error_handler(handler)**: _Set custom error handler_
 - _InMemoryBus_
 - _Default in-memory implementation of EventBus_.

Features:

Thread-safe operations
Automatic async detection
Event queuing for nested emits

---- 

## Decorators

### @listener
Register a function as an event listener.

````Python 
@listener("topic.pattern", priority=0, tags=(), filter_fn=None, once=False)
def my_listener(event: Event) -> Any:
    ...
````

### @rate_limit
Rate limit a listener function.

````Python
@rate_limit(calls=10, period=60.0)
def rate_limited_listener(event: Event):
    ...
````

### @debounce
Debounce a listener function.

```Python
@debounce(interval=0.5)
def debounced_listener(event: Event):
    ...
````


