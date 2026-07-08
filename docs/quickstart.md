
# Quick Start

Get started with Eventful in minutes.

## Installation

```bash
pip install eventful
```
## Basic Usage

````Python
from eventful import Event, emit, listener

# Register a simple listener
@listener("user.created")
def handle_user_created(event):
    print(f"New user: {event.payload}")

# Emit an event
emit(Event(type="user.created", payload="Alice"))
````

# Async Support

````Python
import asyncio
from eventful import Event, emit, listener

@listener("email.sent")
async def send_confirmation(event):
    await asyncio.sleep(0.1)
    print(f"Confirmation sent for: {event.payload}")

# Emit async event
async def main():
    await emit(Event(type="email.sent", payload="user@example.com"))

asyncio.run(main())
````
# Advanced Features
## Priority System

````Python
@listener("order.*", priority=10)  # High priority

def high_priority_handler(event):
    print("Processing urgent order")

@listener("order.*", priority=0)   # Normal priority  
def normal_handler(event):
    print("Processing normal order")
Tag Filtering
@listener("system.alert", tags={"critical"})
def critical_alert_handler(event):
    send_alert_to_admin(event.payload)

emit(Event(type="system.alert", payload="Server down", tags={"critical"}))

````

Next Steps
Learn about Advanced Configuration [blocked]
Explore Framework Integration [blocked]
See Real-world Examples [blocked]