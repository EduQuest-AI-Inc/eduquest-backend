import pytest
from unittest.mock import MagicMock, AsyncMock

from bots._mocks import MockPptxAgent
from services.slides.pptx_generation_service import PptxGenerationService
from exceptions.validation_error import ValidationError


def _mock_agent(raises=None):
    """Wrap MockPptxAgent; override run() to raise when testing the error path."""
    agent = MockPptxAgent()
    if raises:
        agent.run = AsyncMock(side_effect=raises)
    return agent


def _svc(agent=None):
    provider = MagicMock()
    if agent is not None:
        provider.create_pptx_agent.return_value = agent
    s3 = MagicMock()
    s3.upload_pptx.return_value = "pptx/p1/l1.pptx"
    s3.upload_html.return_value = "pptx/p1/l1.html"
    return PptxGenerationService(
        bot_provider=provider,
        lesson_pptx_dao=MagicMock(),
        period_dao=MagicMock(),
        lesson_dao=MagicMock(),
        concept_dao=MagicMock(),
        skill_dao=MagicMock(),
        concept_skill_dao=MagicMock(),
        s3=s3,
    )


def _curriculum(lesson_id="l1", lesson_name="Algebra Basics"):
    # Field names mirror the DB columns: lesson.lesson_id, lesson.lesson_name,
    # concept.concept_name, concept.lesson_name, skill.skill_name,
    # concept_skill.concept_name, concept_skill.skill_name
    return {
        "lessons": [{"lesson_id": lesson_id, "lesson_name": lesson_name}],
        "concepts": [{"concept_name": "Variables", "lesson_name": lesson_name}],
        "skills": [{"skill_name": "Solve for x", "concept_name": "Variables"}],
        "concept_skills": [{"concept_name": "Variables", "skill_name": "Solve for x"}],
    }


def _period_context():
    return {
        "period_name": "Period 1",
        "grade_level": "9",
        "course_name": "Algebra I",
        "course_description": "Introduction to algebra",
    }


def _period_row():
    return {
        "name": "Period 1",
        "grade_level": "9",
        "canvas_course_name": "Algebra I",
        "course_description": "Introduction to algebra",
    }


def _pptx_row(pptx_id="px1", lesson_id="l1", period_id="p1", status="pending"):
    return {"pptx_id": pptx_id, "lesson_id": lesson_id, "period_id": period_id, "status": status}


# ── start_batch — guard ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_start_batch_raises_if_already_running():
    svc = _svc()
    svc.lesson_pptx_dao.get_by_period.return_value = [_pptx_row()]
    with pytest.raises(ValidationError):
        svc.start_batch("p1", MagicMock(), [{"lesson_id": "l1"}])


# ── start_batch — record insertion ───────────────────────────────────────────

@pytest.mark.unit
def test_start_batch_inserts_one_record_per_lesson():
    svc = _svc()
    svc.lesson_pptx_dao.get_by_period.return_value = []
    lessons = [{"lesson_id": "l1"}, {"lesson_id": "l2"}]
    svc.start_batch("p1", MagicMock(), lessons)
    assert svc.lesson_pptx_dao.insert.call_count == 2


# ── start_batch — background task ────────────────────────────────────────────

@pytest.mark.unit
def test_start_batch_schedules_run_batch():
    svc = _svc()
    svc.lesson_pptx_dao.get_by_period.return_value = []
    bg = MagicMock()
    svc.start_batch("p1", bg, [{"lesson_id": "l1"}])
    bg.add_task.assert_called_once_with(svc.run_batch, "p1")


@pytest.mark.unit
def test_start_batch_returns_lesson_count():
    svc = _svc()
    svc.lesson_pptx_dao.get_by_period.return_value = []
    lessons = [{"lesson_id": "l1"}, {"lesson_id": "l2"}, {"lesson_id": "l3"}]
    count = svc.start_batch("p1", MagicMock(), lessons)
    assert count == 3


# ── run_batch — curriculum assembly ──────────────────────────────────────────

@pytest.mark.unit
def test_run_batch_builds_curriculum_from_all_daos():
    svc = _svc(agent=_mock_agent())
    svc.period_dao.get_period_by_id.return_value = _period_row()
    svc.lesson_pptx_dao.get_by_period.return_value = [_pptx_row()]
    svc.lesson_dao.get_lessons_by_period.return_value = []
    svc.concept_dao.get_concepts_by_period.return_value = []
    svc.skill_dao.get_skills_by_period.return_value = []
    svc.concept_skill_dao.get_all_for_period.return_value = []

    svc.run_batch("p1")

    svc.lesson_dao.get_lessons_by_period.assert_called_once_with("p1")
    svc.concept_dao.get_concepts_by_period.assert_called_once_with("p1")
    svc.skill_dao.get_skills_by_period.assert_called_once_with("p1")
    svc.concept_skill_dao.get_all_for_period.assert_called_once_with("p1")


# ── run_batch — happy path (pptx + html) ─────────────────────────────────────

@pytest.mark.unit
def test_run_batch_happy_path_pptx_and_html():
    svc = _svc(agent=_mock_agent())
    svc.period_dao.get_period_by_id.return_value = _period_row()
    svc.lesson_pptx_dao.get_by_period.return_value = [_pptx_row()]
    svc.lesson_dao.get_lessons_by_period.return_value = _curriculum()["lessons"]
    svc.concept_dao.get_concepts_by_period.return_value = _curriculum()["concepts"]
    svc.skill_dao.get_skills_by_period.return_value = _curriculum()["skills"]
    svc.concept_skill_dao.get_all_for_period.return_value = _curriculum()["concept_skills"]

    svc.run_batch("p1")

    calls = svc.lesson_pptx_dao.update_status.call_args_list
    statuses = [c[0][1].get("status") for c in calls]
    assert "generating" in statuses
    assert "done" in statuses

    done_fields = next(c[0][1] for c in calls if c[0][1].get("status") == "done")
    assert done_fields.get("s3_key") == "pptx/p1/l1.pptx"
    assert done_fields.get("html_key") is not None  # html_str is non-empty from MockPptxAgent

    svc._s3.upload_pptx.assert_called_once()
    svc._s3.upload_html.assert_called_once()


# ── run_batch — lesson not in curriculum ─────────────────────────────────────

@pytest.mark.unit
def test_run_batch_missing_lesson_writes_failed():
    svc = _svc(agent=_mock_agent())
    svc.period_dao.get_period_by_id.return_value = _period_row()
    svc.lesson_pptx_dao.get_by_period.return_value = [_pptx_row(lesson_id="missing")]
    svc.lesson_dao.get_lessons_by_period.return_value = _curriculum()["lessons"]
    svc.concept_dao.get_concepts_by_period.return_value = _curriculum()["concepts"]
    svc.skill_dao.get_skills_by_period.return_value = _curriculum()["skills"]
    svc.concept_skill_dao.get_all_for_period.return_value = _curriculum()["concept_skills"]

    svc.run_batch("p1")

    svc.lesson_pptx_dao.update_status.assert_called_once_with("px1", {"status": "failed"})
    svc._s3.upload_pptx.assert_not_called()


# ── run_batch — partial failure ───────────────────────────────────────────────

@pytest.mark.unit
def test_run_batch_partial_failure():
    svc = _svc(agent=_mock_agent())
    svc.period_dao.get_period_by_id.return_value = _period_row()
    svc.lesson_pptx_dao.get_by_period.return_value = [
        _pptx_row(pptx_id="px1", lesson_id="l1"),
        _pptx_row(pptx_id="px2", lesson_id="missing"),
    ]
    svc.lesson_dao.get_lessons_by_period.return_value = _curriculum()["lessons"]
    svc.concept_dao.get_concepts_by_period.return_value = _curriculum()["concepts"]
    svc.skill_dao.get_skills_by_period.return_value = _curriculum()["skills"]
    svc.concept_skill_dao.get_all_for_period.return_value = _curriculum()["concept_skills"]

    svc.run_batch("p1")

    statuses = [c[0][1].get("status") for c in svc.lesson_pptx_dao.update_status.call_args_list]
    assert "done" in statuses
    assert "failed" in statuses


# ── run_batch — agent raises → status written as "failed" ────────────────────

@pytest.mark.unit
def test_run_batch_agent_raises_writes_failed():
    svc = _svc(agent=_mock_agent(raises=RuntimeError("agent exploded")))
    svc.period_dao.get_period_by_id.return_value = _period_row()
    svc.lesson_pptx_dao.get_by_period.return_value = [_pptx_row()]
    svc.lesson_dao.get_lessons_by_period.return_value = _curriculum()["lessons"]
    svc.concept_dao.get_concepts_by_period.return_value = _curriculum()["concepts"]
    svc.skill_dao.get_skills_by_period.return_value = _curriculum()["skills"]
    svc.concept_skill_dao.get_all_for_period.return_value = _curriculum()["concept_skills"]

    svc.run_batch("p1")  # must not propagate

    statuses = [c[0][1].get("status") for c in svc.lesson_pptx_dao.update_status.call_args_list]
    assert statuses == ["generating", "failed"]


# ── run_batch — agent timeout → status written as "failed" ───────────────────

@pytest.mark.unit
def test_run_batch_agent_timeout_writes_failed():
    import asyncio
    svc = _svc(agent=_mock_agent(raises=asyncio.TimeoutError()))
    svc.period_dao.get_period_by_id.return_value = _period_row()
    svc.lesson_pptx_dao.get_by_period.return_value = [_pptx_row()]
    svc.lesson_dao.get_lessons_by_period.return_value = _curriculum()["lessons"]
    svc.concept_dao.get_concepts_by_period.return_value = _curriculum()["concepts"]
    svc.skill_dao.get_skills_by_period.return_value = _curriculum()["skills"]
    svc.concept_skill_dao.get_all_for_period.return_value = _curriculum()["concept_skills"]

    svc.run_batch("p1")  # must not propagate

    statuses = [c[0][1].get("status") for c in svc.lesson_pptx_dao.update_status.call_args_list]
    assert statuses == ["generating", "failed"]
