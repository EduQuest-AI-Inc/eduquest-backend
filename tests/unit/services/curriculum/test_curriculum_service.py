import pytest
from unittest.mock import MagicMock, patch

from services.curriculum.curriculum_service import CurriculumService
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError


def _svc():
    svc = CurriculumService.__new__(CurriculumService)
    svc._bot_provider = MagicMock()
    svc.period_dao = MagicMock()
    svc.week_dao = MagicMock()
    svc.lesson_dao = MagicMock()
    svc.concept_dao = MagicMock()
    svc.skill_dao = MagicMock()
    svc.concept_skill_dao = MagicMock()
    return svc


def _period(status="pending"):
    return {"period_id": "p1", "name": "Bio 101", "status": status}


# ── trigger_generation ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_trigger_generation_enqueues_background_task():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("pending")
    bg = MagicMock()
    svc.trigger_generation("p1", bg)
    bg.add_task.assert_called_once()
    args = bg.add_task.call_args[0]
    assert args[0] == svc._run_generation
    assert args[1] == "p1"


@pytest.mark.unit
def test_trigger_generation_draft_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    with pytest.raises(ValidationError):
        svc.trigger_generation("p1", MagicMock())


@pytest.mark.unit
def test_trigger_generation_approved_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("approved")
    with pytest.raises(ValidationError):
        svc.trigger_generation("p1", MagicMock())


@pytest.mark.unit
def test_trigger_generation_period_not_found_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None
    with pytest.raises(NotFoundError):
        svc.trigger_generation("p1", MagicMock())


# ── get_curriculum ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_curriculum_returns_all_sections():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    svc.week_dao.get_weeks_by_period.return_value = [{"week_number": 1}]
    svc.lesson_dao.get_lessons_by_period.return_value = [{"lesson_name": "L1"}]
    svc.concept_dao.get_concepts_by_period.return_value = [{"concept_name": "C1"}]
    svc.skill_dao.get_skills_by_period.return_value = [{"skill_name": "S1"}]
    svc.concept_skill_dao.get_all_for_period.return_value = [{"concept_name": "C1", "skill_name": "S1"}]

    result = svc.get_curriculum("p1")

    assert result["period_status"] == "draft"
    assert len(result["weeks"]) == 1
    assert len(result["lessons"]) == 1
    assert len(result["concepts"]) == 1
    assert len(result["skills"]) == 1
    assert len(result["concept_skills"]) == 1


@pytest.mark.unit
def test_get_curriculum_period_not_found_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None
    with pytest.raises(NotFoundError):
        svc.get_curriculum("p1")


# ── save_curriculum ───────────────────────────────────────────────────────────

_PAYLOAD = {
    "weeks": [{"week_number": 1, "week_start": None, "week_end": None}],
    "lessons": [{"lesson_name": "Intro", "week_number": 1}],
    "concepts": [{"concept_name": "DNA", "lesson_name": "Intro"}],
    "skills": [{"skill_name": "Recall", "mastery_threshold": 0.8}],
    "concept_skills": [{"concept_name": "DNA", "skill_name": "Recall"}],
}


@pytest.mark.unit
def test_save_curriculum_inserts_all_entities():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    svc.lesson_dao.insert_lesson.return_value = "lesson-id-1"
    svc.save_curriculum("p1", _PAYLOAD)
    svc.week_dao.insert_week.assert_called_once()
    svc.lesson_dao.insert_lesson.assert_called_once()
    svc.concept_dao.insert_concept.assert_called_once()
    svc.skill_dao.insert_skill.assert_called_once()
    svc.concept_skill_dao.insert_concept_skill.assert_called_once()


@pytest.mark.unit
def test_save_curriculum_period_not_found_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None
    with pytest.raises(NotFoundError):
        svc.save_curriculum("p1", _PAYLOAD)


@pytest.mark.unit
def test_save_curriculum_dao_error_propagates():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    svc.week_dao.insert_week.side_effect = RuntimeError("db error")
    with pytest.raises(RuntimeError, match="db error"):
        svc.save_curriculum("p1", _PAYLOAD)


# ── update_concept ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_update_concept_happy_path():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    svc.concept_dao.get_concept.return_value = {"concept_name": "DNA"}
    svc.update_concept("p1", "DNA", {"description": "new"})
    svc.concept_dao.update_concept.assert_called_once()


@pytest.mark.unit
def test_update_concept_not_found_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    svc.concept_dao.get_concept.return_value = None
    with pytest.raises(NotFoundError):
        svc.update_concept("p1", "Missing", {"description": "x"})


@pytest.mark.unit
def test_update_concept_period_not_found_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None
    with pytest.raises(NotFoundError):
        svc.update_concept("p1", "DNA", {"description": "x"})


# ── update_skill ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_update_skill_happy_path():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    svc.update_skill("p1", "Recall", {"bloom_level": "Remember"})
    svc.skill_dao.update_skill.assert_called_once()


@pytest.mark.unit
def test_update_skill_period_not_found_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None
    with pytest.raises(NotFoundError):
        svc.update_skill("p1", "Recall", {"bloom_level": "Remember"})


# ── approve_period ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_approve_period_draft_transitions_to_approved():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("draft")
    svc.lesson_dao.get_lessons_by_period.return_value = [{"lesson_id": "l1", "lesson_name": "Intro"}]
    bg = MagicMock()
    with patch("data_access.lesson_pptx_dao.LessonPptxDAO") as MockDao, \
         patch("services.pptx.pptx_generation_service.PptxGenerationService"):
        MockDao.return_value.get_by_period.return_value = []
        svc.approve_period("p1", bg)
    called_status = svc.period_dao.update_status.call_args[0][1]
    assert called_status == "approved"


@pytest.mark.unit
def test_approve_period_pending_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("pending")
    with pytest.raises(ValidationError):
        svc.approve_period("p1", MagicMock())


@pytest.mark.unit
def test_approve_period_already_approved_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = _period("approved")
    with pytest.raises(ValidationError):
        svc.approve_period("p1", MagicMock())


@pytest.mark.unit
def test_approve_period_period_not_found_raises():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None
    with pytest.raises(NotFoundError):
        svc.approve_period("p1", MagicMock())
