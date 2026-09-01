#!/bin/sh
# Dockerfile.web's CMD. Runs migrations, seeds the two demo tenants on a
# genuinely empty database only, then starts the API. Idempotent: a restart
# against a volume that already has data re-runs migrations (a no-op once
# they are applied) and skips the seed (see scripts/seed_if_empty.py).
set -e

echo "web-entrypoint: running migrations"
alembic upgrade head

echo "web-entrypoint: seeding demo data if the database is empty"
python scripts/seed_if_empty.py

echo "web-entrypoint: starting uvicorn"
exec uvicorn main:app --host 0.0.0.0 --port 8000
