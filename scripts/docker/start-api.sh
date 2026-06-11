#!/usr/bin/env sh
set -eu

python -m alembic upgrade head
exec uvicorn semantic_lighthouse.main:app --host 0.0.0.0 --port 8000 --workers "${API_WORKERS:-1}"
