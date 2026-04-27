#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
exec .venv/bin/python -m uvicorn main:app --reload \
  --reload-dir api \
  --reload-dir services \
  --reload-dir models \
  --reload-dir utils \
  --reload-dir exceptions \
  --reload-dir constants \
  --reload-dir EQ_agents \
  --reload-dir routes \
  --reload-dir data_access \
  --reload-dir integrations \
  --host 0.0.0.0 \
  --port 8000
