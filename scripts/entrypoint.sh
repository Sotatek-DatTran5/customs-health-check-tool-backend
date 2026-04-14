#!/bin/bash
set -e

echo "[entrypoint] Running database migrations..."
uv run alembic upgrade head

echo "[entrypoint] Starting application..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8329
