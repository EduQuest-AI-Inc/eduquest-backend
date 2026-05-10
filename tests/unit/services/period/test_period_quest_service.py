import pytest
from unittest.mock import MagicMock, patch

from services.period.period_quest_service import PeriodQuestService
from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError


STUDENT_ID = "student-1"
PERIOD_ID = "period-1"


def _svc():
    svc = PeriodQuestService.__new__(PeriodQuestService)
    svc.period_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.enrollment_dao = MagicMock()
    svc.curriculum_service = MagicMock()
    svc.ltg_conversation_dao = MagicMock()
    svc.ltg_goal_dao = MagicMock()
    svc.quest_service = MagicMock()
    return svc


def _enrolled_svc():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": STUDENT_ID}]
    return svc


def _minimal_curriculum():
    return {
        "weeks": [{"week_number": 1}],
        "lessons": [{"week_number": 1, "lesson_name": "Intro to Python"}],
        "concepts": [{"lesson_name": "Intro to Python", "concept_name": "Variables"}],
    }


def _mock_provider_with_hw():
    provider = MagicMock()
    hw_agent = MagicMock()
    hw_agent.run.return_value = {"list_of_quests": []}
    provider.create_hw_agent.return_value = hw_agent
    return provider


# ---- start_homework_agent ----

@pytest.mark.unit
def test_start_homework_agent_not_enrolled():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": "other"}]

    with pytest.raises(ValidationError):
        svc.start_homework_agent(STUDENT_ID, PERIOD_ID)


@pytest.mark.unit
def test_start_homework_agent_student_not_found():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.start_homework_agent(STUDENT_ID, PERIOD_ID)


@pytest.mark.unit
def test_start_homework_agent_period_not_found():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.start_homework_agent(STUDENT_ID, PERIOD_ID)


@pytest.mark.unit
def test_start_homework_agent_no_curriculum_weeks():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID}
    svc.curriculum_service.get_curriculum.return_value = {"weeks": [], "lessons": [], "concepts": []}

    with pytest.raises(NotFoundError):
        svc.start_homework_agent(STUDENT_ID, PERIOD_ID)


@pytest.mark.unit
def test_start_homework_agent_no_ltg_conversation():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID}
    svc.curriculum_service.get_curriculum.return_value = _minimal_curriculum()
    svc.ltg_conversation_dao.get_conversation_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.start_homework_agent(STUDENT_ID, PERIOD_ID)


@pytest.mark.unit
def test_start_homework_agent_happy_path_with_goal():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID, "start_date": "2024-01-08"}
    svc.curriculum_service.get_curriculum.return_value = _minimal_curriculum()
    svc.ltg_conversation_dao.get_conversation_id.return_value = "conv-1"
    svc.ltg_conversation_dao.get_last_response_id.return_value = "resp-1"
    svc.ltg_goal_dao.get_by_student_and_period.return_value = "Build a capstone project"
    svc.quest_service.update_quests_preserving_completed_data.return_value = {"saved": True}

    provider = _mock_provider_with_hw()
    schedule_agent = MagicMock()
    schedule_agent.run.return_value = MagicMock(quests=[])
    provider.create_schedule_agent.return_value = schedule_agent

    with patch("services.period.period_quest_service.get_bot_provider", return_value=provider):
        result = svc.start_homework_agent(STUDENT_ID, PERIOD_ID)

    assert "homework" in result
    assert "saved_quests" in result
    assert "Homework generated" in result["message"]
    provider.create_schedule_agent.assert_called_once()
    provider.create_hw_agent.assert_called_once()


@pytest.mark.unit
def test_start_homework_agent_happy_path_no_goal():
    """When no LTG goal exists, schedule enrichment is skipped but homework is still generated."""
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID}
    svc.curriculum_service.get_curriculum.return_value = _minimal_curriculum()
    svc.ltg_conversation_dao.get_conversation_id.return_value = "conv-1"
    svc.ltg_conversation_dao.get_last_response_id.return_value = "resp-1"
    svc.ltg_goal_dao.get_by_student_and_period.return_value = None
    svc.quest_service.update_quests_preserving_completed_data.return_value = {}

    provider = _mock_provider_with_hw()

    with patch("services.period.period_quest_service.get_bot_provider", return_value=provider):
        result = svc.start_homework_agent(STUDENT_ID, PERIOD_ID)

    assert "homework" in result
    provider.create_schedule_agent.assert_not_called()
    provider.create_hw_agent.assert_called_once()


@pytest.mark.unit
def test_start_homework_agent_schedule_agent_failure_falls_back():
    """If the schedule agent raises, service falls back to generic names and still completes."""
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID}
    svc.curriculum_service.get_curriculum.return_value = _minimal_curriculum()
    svc.ltg_conversation_dao.get_conversation_id.return_value = "conv-1"
    svc.ltg_conversation_dao.get_last_response_id.return_value = "resp-1"
    svc.ltg_goal_dao.get_by_student_and_period.return_value = "Build something"
    svc.quest_service.update_quests_preserving_completed_data.return_value = {}

    provider = _mock_provider_with_hw()
    schedule_agent = MagicMock()
    schedule_agent.run.side_effect = RuntimeError("OpenAI timeout")
    provider.create_schedule_agent.return_value = schedule_agent

    with patch("services.period.period_quest_service.get_bot_provider", return_value=provider):
        result = svc.start_homework_agent(STUDENT_ID, PERIOD_ID)

    assert "homework" in result
    provider.create_hw_agent.assert_called_once()


# ---- update_quests_with_recommended_change ----

@pytest.mark.unit
def test_update_quests_not_enrolled():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = []

    with pytest.raises(ValidationError):
        svc.update_quests_with_recommended_change(STUDENT_ID, "student", PERIOD_ID, "add more math")


@pytest.mark.unit
def test_update_quests_student_not_found():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.update_quests_with_recommended_change(STUDENT_ID, "student", PERIOD_ID, "add more math")


@pytest.mark.unit
def test_update_quests_period_not_found():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.update_quests_with_recommended_change(STUDENT_ID, "student", PERIOD_ID, "add more math")


@pytest.mark.unit
def test_update_quests_no_existing_quests():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID}
    svc.quest_service.get_quests_for_student_and_period.return_value = []

    with pytest.raises(NotFoundError):
        svc.update_quests_with_recommended_change(STUDENT_ID, "student", PERIOD_ID, "add more math")


@pytest.mark.unit
def test_update_quests_all_completed_is_noop():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID}
    svc.quest_service.get_quests_for_student_and_period.return_value = [
        {"description": "Q1", "skills": "s1", "week": 1, "grade": 4.5, "status": "completed"},
        {"description": "Q2", "skills": "s2", "week": 2, "grade": None, "status": "completed"},
    ]

    result = svc.update_quests_with_recommended_change(STUDENT_ID, "student", PERIOD_ID, "change")

    assert result["affected_quests"] == 0
    assert result["preserved_quests"] == 2
    svc.quest_service.update_quests_preserving_completed_data.assert_not_called()


@pytest.mark.unit
def test_update_quests_happy_path():
    svc = _enrolled_svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": STUDENT_ID}
    svc.period_dao.get_period_by_id.return_value = {"period_id": PERIOD_ID}
    svc.quest_service.get_quests_for_student_and_period.return_value = [
        {"description": "Q1", "skills": "Reading", "week": 1, "grade": None, "status": "pending"},
        {"description": "Q2", "skills": "Writing", "week": 2, "grade": 5.0, "status": "completed"},
    ]
    svc.ltg_conversation_dao.get_last_response_id.return_value = "resp-1"
    svc.quest_service.update_quests_preserving_completed_data.return_value = {"updated": True}

    provider = _mock_provider_with_hw()

    with patch("services.period.period_quest_service.get_bot_provider", return_value=provider):
        result = svc.update_quests_with_recommended_change(STUDENT_ID, "student", PERIOD_ID, "add more math")

    assert result["affected_quests"] == 1
    assert result["preserved_quests"] == 1
    assert result["updated_quests"] == 1
    assert result["total_quests"] == 2
    assert result["recommended_change"] == "add more math"
    provider.create_hw_agent.assert_called_once()
