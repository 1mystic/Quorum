#!/bin/sh
# Dockerfile.worker's CMD. Waits for the schema to exist (the web container
# applies migrations; this runs `alembic upgrade head` too so the worker is
# never left waiting on a schema forever if it starts first) then loops
# materialize_insights.py forever.
set -e

echo "worker-entrypoint: running migrations"
alembic upgrade head

echo "worker-entrypoint: starting the materialization loop"
exec python scripts/materialize_insights.py
