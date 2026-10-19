#!/usr/bin/env bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

PORT="${PORT:-8000}"
echo "Starting application on port ${PORT}..."

if [ "$#" -eq 0 ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
elif [ "$1" = "uvicorn" ]; then
    # In Cloud Run or production, ensure PORT is respected
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
fi

exec "$@"
