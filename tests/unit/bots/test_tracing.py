import sys

import pytest


class _FakeRunConfig:
    def __init__(self):
        self.workflow_name = "Existing workflow"
        self.group_id = "existing-group"
        self.trace_metadata = {"keep": "yes", "drop": {"nested": "no"}}
        self.trace_include_sensitive_data = False
        self.previous_response_id = "untouched"


@pytest.mark.unit
def test_build_trace_run_config_merges_trace_settings_without_dropping_fields(monkeypatch):
    from bots.tracing import build_trace_run_config, hashed_trace_group_id

    monkeypatch.setattr(sys.modules["agents"], "RunConfig", _FakeRunConfig, raising=False)
    existing = _FakeRunConfig()

    result = build_trace_run_config(
        existing,
        workflow_name="profile_conversation",
        group_id="response-123",
        metadata={"phase": "continue", "unsafe": ["not scalar"], "count": 2},
    )

    assert result.workflow_name == "profile_conversation"
    assert result.group_id == hashed_trace_group_id("response-123")
    assert result.trace_include_sensitive_data is False
    assert result.trace_metadata == {"keep": "yes", "phase": "continue", "count": 2}
    assert result.previous_response_id == "untouched"
    assert result is not existing


@pytest.mark.unit
def test_hashed_trace_group_id_is_stable_and_not_raw():
    from bots.tracing import hashed_trace_group_id

    first = hashed_trace_group_id("student-or-response-id")
    second = hashed_trace_group_id("student-or-response-id")

    assert first == second
    assert first.startswith("hash_")
    assert "student-or-response-id" not in first
