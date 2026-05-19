#!/usr/bin/env bash
set -e
venv/bin/python -c "import json; from main import app; print(json.dumps(app.openapi()))" > openapi.json
if [ -d ../eduquest-frontend ]; then
    cp openapi.json ../eduquest-frontend/openapi.json
else
    echo "WARNING: no frontend directory found — copy openapi.json to eduquest-frontend manually" >&2
fi
