# Release process

Update version, changelog, documentation status tables, run CI checks, build distributions, and publish only from reviewed release commits.

## Local distribution validation

Build the release artifacts once, then test each artifact and optional dependency in
a fresh environment. The following commands are the local equivalent of the CI
installation jobs; both `python3.13` and `python3.14` must complete them.

```bash
(
set -euo pipefail

redis_container=
postgres_container=
cleanup() {
  [ -z "$redis_container" ] || docker rm -f "$redis_container" >/dev/null 2>&1 || true
  [ -z "$postgres_container" ] || docker rm -f "$postgres_container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_healthy() {
  local container=$1
  local service=$2
  local status
  for _ in {1..60}; do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$container")
    case "$status" in
      healthy) return 0 ;;
      unhealthy)
        echo "$service became unhealthy" >&2
        return 1
        ;;
      starting) sleep 1 ;;
      *)
        echo "$service entered unexpected health state: $status" >&2
        return 1
        ;;
    esac
  done
  echo "timed out waiting for $service to become healthy" >&2
  return 1
}

rm -rf dist build .release-build .release-venv-*
python3.13 -m venv .release-build
.release-build/bin/python -m pip install build
.release-build/bin/python -m build

redis_container=$(docker run --rm -d --name eventful-release-redis -p 6379:6379 \
  --health-cmd 'redis-cli ping' --health-interval 1s --health-retries 30 \
  redis:7-alpine)
postgres_container=$(docker run --rm -d --name eventful-release-postgres -p 5432:5432 \
  -e POSTGRES_DB=eventful -e POSTGRES_USER=eventful \
  -e POSTGRES_PASSWORD=eventful --health-cmd 'pg_isready -U eventful -d eventful' \
  --health-interval 1s --health-retries 30 postgres:16-alpine)
wait_for_healthy "$redis_container" Redis
wait_for_healthy "$postgres_container" PostgreSQL
export EVENTFUL_REDIS_URL=redis://localhost:6379/15
export EVENTFUL_POSTGRES_URL=postgresql://eventful:eventful@localhost:5432/eventful

wheel=$(echo dist/*.whl)
sdist=$(echo dist/*.tar.gz)
core_tests=(tests/test_bus.py tests/test_contracts.py tests/test_dispatch.py \
  tests/test_error.py tests/test_event.py tests/test_extensions.py \
  tests/test_file_persistence.py \
  tests/test_import_surface.py tests/test_init.py tests/test_router.py)

for python in python3.13 python3.14; do
  for installation in wheel-core sdist-core redis postgres fastapi starlette; do
    env=".release-venv-${python}-${installation}"
    "$python" -m venv "$env"
    "$env/bin/python" -m pip install pytest pytest-asyncio
    case "$installation" in
      wheel-core) "$env/bin/python" -m pip install "$wheel" ;;
      sdist-core) "$env/bin/python" -m pip install "$sdist" ;;
      *) "$env/bin/python" -m pip install "$wheel[$installation]" ;;
    esac
    case "$installation" in
      wheel-core|sdist-core)
        "$env/bin/python" -c 'import importlib.util; assert all(importlib.util.find_spec(module) is None for module in ("redis", "asyncpg", "fastapi", "starlette")); import eventful, eventful.contracts'
        "$env/bin/python" -m pytest "${core_tests[@]}"
        ;;
      redis)
        "$env/bin/python" -c 'import eventful, eventful.transports.redis, redis.asyncio'
        "$env/bin/python" -m pytest tests/test_redis_transport.py
        ;;
      postgres)
        "$env/bin/python" -c 'import asyncpg, eventful, eventful.persistence.postgres_persistence'
        "$env/bin/python" -m pytest tests/test_postgres_persistence.py
        ;;
      fastapi)
        "$env/bin/python" -c 'import eventful, eventful.adapters.fastapi, fastapi'
        "$env/bin/python" -m pytest tests/test_adapters.py
        ;;
      starlette)
        "$env/bin/python" -c 'import asyncio, eventful, starlette; from eventful.adapters.starlette import EventfulMiddleware; namespace={}; exec("async def app(scope, receive, send):\n    assert scope[\"state\"][\"eventful_bus\"]", namespace); asyncio.run(EventfulMiddleware(namespace["app"])({"type": "http"}, None, None))'
        ;;
    esac
  done
done
)
```
