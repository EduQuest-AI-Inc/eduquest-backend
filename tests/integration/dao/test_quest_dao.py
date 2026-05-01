"""Integration tests for QuestDAO."""
import pytest
from data_access.quest_dao import QuestDAO
from models.quest import Quest

_QUEST_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"


def _quest(user_id, period_id):
    return Quest(
        quest_id=_QUEST_ID,
        user_id=user_id,
        period_id=period_id,
        description="Test Quest",
        skills="algebra",
        week=1,
        instructions="Do the thing",
        rubric={"criterion": "accuracy"},
        status="not_started",
    )


@pytest.mark.integration
def test_add_and_get_by_id(db_period, db_user):
    dao = QuestDAO()
    dao.add_quest(_quest(db_user.user_id, db_period.period_id))
    try:
        result = dao.get_quest_by_id(_QUEST_ID)
        assert result is not None
        assert result["quest_id"] == _QUEST_ID
    finally:
        dao.delete_quest(_QUEST_ID)


@pytest.mark.integration
def test_get_quests_by_student_and_period(db_period, db_user):
    dao = QuestDAO()
    dao.add_quest(_quest(db_user.user_id, db_period.period_id))
    try:
        results = dao.get_quests_by_student_and_period(db_user.user_id, db_period.period_id)
        assert any(r["quest_id"] == _QUEST_ID for r in results)
    finally:
        dao.delete_quest(_QUEST_ID)


@pytest.mark.integration
def test_update_quest_grade_and_feedback(db_period, db_user):
    dao = QuestDAO()
    dao.add_quest(_quest(db_user.user_id, db_period.period_id))
    try:
        grade = {"overall_score": "95/100", "detailed_grade": {"accuracy": 0.95}}
        dao.update_quest_grade_and_feedback(_QUEST_ID, grade, "Great work!")
        result = dao.get_quest_by_id(_QUEST_ID)
        assert isinstance(result["grade"], dict), f"expected dict grade, got {result['grade']!r}"
        assert result["grade"]["overall_score"] == "95/100"
        assert result["status"] == "completed"
    finally:
        dao.delete_quest(_QUEST_ID)


@pytest.mark.integration
def test_update_quest_status(db_period, db_user):
    dao = QuestDAO()
    dao.add_quest(_quest(db_user.user_id, db_period.period_id))
    try:
        dao.update_quest_status(_QUEST_ID, "in_progress")
        result = dao.get_quest_by_id(_QUEST_ID)
        assert result["status"] == "in_progress"
    finally:
        dao.delete_quest(_QUEST_ID)


@pytest.mark.integration
def test_delete_quest(db_period, db_user):
    dao = QuestDAO()
    dao.add_quest(_quest(db_user.user_id, db_period.period_id))
    dao.delete_quest(_QUEST_ID)
    assert dao.get_quest_by_id(_QUEST_ID) is None
