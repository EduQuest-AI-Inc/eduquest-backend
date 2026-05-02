"""
Singleton PostHog client for the FastAPI backend.

Initialized lazily so test runs that don't touch tracking don't need
`POSTHOG_API_KEY`. Lifespan-aware shutdown drains the queue on graceful stop.
"""

from __future__ import annotations

import logging
import os
from typing import Any

try:
    from posthog import Posthog  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - import-time fallback for envs without the lib
    Posthog = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_posthog: Any = None


class _NullPosthog:
    """Drop-in stand-in when posthog is not installed or no API key is set.

    Mirrors the call shape of the real client but does nothing. Lets the rest
    of the backend call into tracking unconditionally.
    """

    def capture(self, *a, **kw) -> None: ...
    def identify(self, *a, **kw) -> None: ...
    def group_identify(self, *a, **kw) -> None: ...
    def alias(self, *a, **kw) -> None: ...
    def shutdown(self) -> None: ...


def get_posthog() -> Any:
    """Return the active PostHog client (real or null)."""
    global _posthog
    if _posthog is not None:
        return _posthog

    api_key = os.environ.get("POSTHOG_API_KEY") or os.environ.get(
        "NEXT_PUBLIC_POSTHOG_KEY"  # tolerate the frontend var name in dev
    )
    if not api_key or Posthog is None:
        logger.info(
            "PostHog disabled (api_key=%s, posthog_installed=%s)",
            bool(api_key),
            Posthog is not None,
        )
        _posthog = _NullPosthog()  # type: ignore[assignment]
        return _posthog

    _posthog = Posthog(
        project_api_key=api_key,
        host=os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com"),
        flush_at=20,
        flush_interval=10,
        # Never raise inside the request handler.
        on_error=lambda err, items: logger.warning("posthog ingest error: %s", err),
    )
    return _posthog


def shutdown_posthog() -> None:
    """Drain the PostHog queue. Wire this into FastAPI's `lifespan` shutdown."""
    global _posthog
    if _posthog is None:
        return
    try:
        _posthog.shutdown()
    except Exception:  # pragma: no cover
        logger.exception("posthog shutdown failed")
    finally:
        _posthog = None
