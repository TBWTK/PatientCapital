#!/bin/sh
set -eu

alembic upgrade head
if [ "$#" -gt 0 ]; then
  exec "$@"
fi
exec uvicorn patientcapital.api.app:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}"
