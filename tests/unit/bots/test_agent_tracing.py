import asyncio
import importlib
import sys
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


@contextmanager
def _recording_context(collection, name, **kwargs):
    collection.append((name, kwargs))
    yield


@pytest.mark.unit
def test_grading_orchestrator_names_outer_trace_and_stage_spans(monkeypatch):
    import bots.grading_agent as grading_agent

    traces = []
    spans = []
    monkeypatch.setattr(
        grading_agent,
        "trace",
        lambda name, **kwargs: _recording_context(traces, name, **kwargs),
    )
    monkeypatch.setattr(
        grading_agent,
        "custom_span",
        lambda name, **kwargs: _recording_context(spans, name, **kwargs),
    )

    numerical = MagicMock(final_output=grading_agent.NumericalGrade(
        criteria_scores={"ideas": 4},
        total_score=8,
        max_possible=10,
    ))
    feedback = MagicMock(final_output=grading_agent.StudentFeedback(feedback="Nice work"))
    mastery = MagicMock(final_output=grading_agent.SkillMastery(skill_mastery={"Writing": 0.8}))
    recommendation = MagicMock(final_output=grading_agent.HomeworkRecommendation(
        changes_recommended=False,
        recommended_changes=None,
    ))
    grading_agent.Runner.run = AsyncMock(
        side_effect=[numerical, feedback, mastery, recommendation]
    )

    orchestrator = grading_agent.GradingOrchestrator.__new__(grading_agent.GradingOrchestrator)
    orchestrator.numerical_agent = MagicMock()
    orchestrator.feedback_agent = MagicMock()
    orchestrator.mastery_agent = MagicMock()
    orchestrator.adaptation_agent = MagicMock()

    result = asyncio.run(orchestrator.grade_submission(
        grading_agent.GradingInput(
            submission="student submission",
            rubric={"ideas": "clear"},
            skills=["Writing"],
            instructions="Write clearly.",
        ),
        trace_group_id="quest-1",
        trace_metadata={"rubric_key_count": 1},
    ))

    assert result.numerical_grade == 8
    assert traces[0][0] == "grading_orchestrator"
    assert traces[0][1]["group_id"].startswith("hash_")
    assert [span[0] for span in spans] == [
        "numerical_grading",
        "student_feedback",
        "skill_mastery",
        "homework_adaptation",
    ]
    assert grading_agent.Runner.run.await_count == 4


@pytest.mark.unit
def test_guardrail_safety_checker_uses_named_span_and_run_config(monkeypatch):
    agents_module = sys.modules["agents"]
    monkeypatch.setattr(agents_module, "input_guardrail", lambda fn: fn, raising=False)
    monkeypatch.setattr(agents_module, "output_guardrail", lambda fn: fn, raising=False)
    monkeypatch.setattr(agents_module, "GuardrailFunctionOutput", _FakeGuardrailFunctionOutput, raising=False)
    monkeypatch.setattr(agents_module, "RunConfig", _FakeRunConfig, raising=False)

    sys.modules.pop("bots.guardrails", None)
    guardrails = importlib.import_module("bots.guardrails")

    spans = []
    monkeypatch.setattr(
        guardrails,
        "custom_span",
        lambda name, **kwargs: _recording_context(spans, name, **kwargs),
    )
    guardrails.Runner.run = AsyncMock(return_value=MagicMock(
        final_output=guardrails.SafetyCheck(is_safe=True, reason="ok")
    ))

    ctx = MagicMock()
    ctx.context = {"trace": "context"}
    result = asyncio.run(guardrails.check_student_input_safety(ctx, MagicMock(), "hello"))

    assert result.tripwire_triggered is False
    assert spans[0][0] == "student_input_safety_check"
    run_config = guardrails.Runner.run.call_args[1]["run_config"]
    assert run_config.workflow_name == "student_input_safety_check"
    assert run_config.trace_metadata == {"guardrail_type": "input"}


@pytest.mark.unit
def test_coverage_evaluator_wraps_direct_openai_call_in_trace_and_generation_span(monkeypatch):
    import bots.curriculum.coverage_evaluator as coverage_evaluator

    traces = []
    generation_spans = []
    generation_span = _FakeGenerationSpan(generation_spans)
    monkeypatch.setattr(
        coverage_evaluator,
        "trace",
        lambda name, **kwargs: _recording_context(traces, name, **kwargs),
    )
    monkeypatch.setattr(
        coverage_evaluator,
        "generation_span",
        lambda **kwargs: generation_span.record(**kwargs),
    )

    parsed = coverage_evaluator.CoverageResult(
        sufficient=True,
        gaps=[],
        research_queries=[],
    )
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(parsed=parsed))]
    completion.usage = None

    evaluator = coverage_evaluator.CoverageEvaluator.__new__(coverage_evaluator.CoverageEvaluator)
    evaluator._client = MagicMock()
    evaluator._client.beta.chat.completions.parse.return_value = completion

    result = evaluator.evaluate(
        course_name="Biology",
        course_description="Cells and genetics",
        has_files=False,
        grade_level="9",
    )

    assert result == parsed
    assert traces[0][0] == "coverage_evaluation"
    assert generation_spans[0]["model"] == coverage_evaluator.COVERAGE_EVALUATOR_MODEL
    assert generation_span.span_data.output[0]["role"] == "assistant"
    evaluator._client.beta.chat.completions.parse.assert_called_once()


class _FakeRunConfig:
    def __init__(self):
        self.workflow_name = "Existing"
        self.group_id = None
        self.trace_metadata = None
        self.trace_include_sensitive_data = False


class _FakeGuardrailFunctionOutput:
    def __init__(self, *, output_info, tripwire_triggered):
        self.output_info = output_info
        self.tripwire_triggered = tripwire_triggered


class _FakeGenerationSpan:
    def __init__(self, collection):
        self.collection = collection
        self.span_data = MagicMock()
        self.span_data.output = None
        self.span_data.usage = None

    def record(self, **kwargs):
        self.collection.append(kwargs)
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
