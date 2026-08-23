# Runnable examples

The repository's `examples/` directory contains standalone programs built
exclusively on Eventful's public API.
The links from the integration guides target this published page so they remain
valid in the generated documentation. The paths below identify the canonical
source files, which the documentation test imports and executes directly.

## Local dispatch

Canonical source: `examples/local_dispatch.py`

```bash
pip install -e .
python examples/local_dispatch.py
```

## Redis Pub/Sub

Canonical source: `examples/redis_pubsub.py`

```bash
pip install -e '.[redis]'
EVENTFUL_REDIS_URL=redis://localhost:6379/0 python examples/redis_pubsub.py
```

## PostgreSQL persistence

Canonical source: `examples/postgres_persistence.py`

```bash
pip install -e '.[postgres]'
EVENTFUL_POSTGRES_URL=postgresql://localhost/eventful python examples/postgres_persistence.py
```

## FastAPI

Canonical source: `examples/fastapi_example.py`

```bash
pip install -e '.[fastapi]' uvicorn
python -m examples.fastapi_example
uvicorn examples.fastapi_example:app
```

## Starlette

Canonical source: `examples/starlette_example.py`

```bash
pip install -e '.[starlette]' uvicorn
python -m examples.starlette_example
uvicorn examples.starlette_example:app
```
