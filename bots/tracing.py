"""Tracing helpers for OpenAI Agents SDK runs.

Keep custom trace metadata intentionally small. The SDK may capture prompts and
outputs in generation spans, but app-provided metadata should stay scalar and
free of names, submissions, secrets, and other high-risk context.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any


_SCALAR_TYPES = (str, int, float, bool)


def hashed_trace_group_id(correlation_id: Any) -> str | None:
    """Return a stable, non-reversible group id for trace correlation."""
    if correlation_id is None:
        return None
    raw = str(correlation_id).strip()
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"hash_{digest[:32]}"


def sanitize_trace_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only simple scalar metadata values."""
    if not metadata:
        return {}
    return {
        str(key): value
        for key, value in metadata.items()
        if value is not None and isinstance(value, _SCALAR_TYPES)
    }


def build_trace_run_config(
    run_config: Any | None = None,
    *,
    workflow_name: str | None = None,
    group_id: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Merge trace settings into an Agents SDK RunConfig.

    The import stays inside the helper so provider imports remain lightweight.
    """
    from agents import RunConfig

    config = copy.copy(run_config) if run_config is not None else RunConfig()
    if workflow_name:
        config.workflow_name = workflow_name
    hashed_group_id = hashed_trace_group_id(group_id)
    if hashed_group_id:
        config.group_id = hashed_group_id

    merged_metadata = sanitize_trace_metadata(getattr(config, "trace_metadata", None))
    merged_metadata.update(sanitize_trace_metadata(metadata))
    config.trace_metadata = merged_metadata or None
    config.trace_include_sensitive_data = False
    return config
