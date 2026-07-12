"""Allowed frontend origins.

Single source of truth for both CORS (``main.py``) and the Stripe redirect-URL
resolver (``routers/billing.py``). Keeping these in one list prevents the two
from drifting — an origin trusted for CORS is also the only kind of origin we
will echo back into a Stripe redirect URL (open-redirect protection).
"""
from __future__ import annotations

ALLOWED_FRONTEND_ORIGINS = [
    "https://eduquestai.org",
    "https://www.eduquestai.org",
    "http://eduquestai.org",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
