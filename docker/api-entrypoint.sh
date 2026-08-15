#!/bin/sh
set -eu

alembic upgrade head
exec uvicorn patientcapital.api.app:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}"
