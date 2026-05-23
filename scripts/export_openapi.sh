#!/usr/bin/env bash
set -e
venv/bin/python -c "import json; from main import app; print(json.dumps(app.openapi()))" > openapi.json
if [ -d ../eduquest-frontend ]; then
    cp openapi.json ../eduquest-frontend/openapi.json
else
    echo "WARNING: no frontend directory found — expected eduquest-frontend to be in the same parent folder as eduquest-backend. Copy openapi.json to eduquest-frontend manually, or check all 3 READMEs for correct setup." >&2
fi
