"""
Integration tests for QuestDAO.
Requires user + period FK rows; creates them inline.
"""
import pytest
from data_access.quest_dao import QuestDAO
from data_access.period_dao import PeriodDAO
from data_access.user_dao import UserDAO
from models.quest import Quest
from models.period import Period
from models.user import User

_QUEST_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
_USER_ID = "test-step8-quest-user"
_PERIOD_ID = "test-step8-quest-period"


def _setup(period_dao, user_dao):
    period_dao.add_period(Period(period_id=_PERIOD_ID, owner_id="owner", name="Quest Test Period", vector_store_id="vs"))
    user_dao.add_user(User(
        user_id=_USER_ID, first_name="Q", last_name="User",
        email="test-step8-quest@example.com", password="pw", role="student",
    ))


def _teardown(quest_dao, period_dao, user_dao):
    try:
        quest_dao.delete_quest(_QUEST_ID)
    except Exception:
        pass
    period_dao.delete_period(_PERIOD_ID)
    user_dao.delete(_USER_ID)


def _quest():
    return Quest(
        quest_id=_QUEST_ID,
        user_id=_USER_ID,
        period_id=_PERIOD_ID,
        description="Test Quest",
        skills="algebra",
        week=1,
        instructions="Do the thing",
        rubric={"criterion": "accuracy"},
        status="not_started",
    )


@pytest.mark.integration
def test_add_and_get_by_id(supabase_required):
    dao = QuestDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.add_quest(_quest())
        result = dao.get_quest_by_id(_QUEST_ID)
        assert result is not None
        assert result["quest_id"] == _QUEST_ID
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_get_quests_by_student_and_period(supabase_required):
    dao = QuestDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.add_quest(_quest())
        results = dao.get_quests_by_student_and_period(_USER_ID, _PERIOD_ID)
        assert any(r["quest_id"] == _QUEST_ID for r in results)
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_update_quest_grade_and_feedback(supabase_required):
    dao = QuestDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.add_quest(_quest())
        grade = {"overall_score": "95/100", "detailed_grade": {"accuracy": 0.95}}
        dao.update_quest_grade_and_feedback(_QUEST_ID, grade, "Great work!")
        result = dao.get_quest_by_id(_QUEST_ID)
        assert isinstance(result["grade"], dict), f"expected dict grade, got {result['grade']!r}"
        assert result["grade"]["overall_score"] == "95/100"
        assert result["status"] == "completed"
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_update_quest_status(supabase_required):
    dao = QuestDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.add_quest(_quest())
        dao.update_quest_status(_QUEST_ID, "in_progress")
        result = dao.get_quest_by_id(_QUEST_ID)
        assert result["status"] == "in_progress"
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_delete_quest(supabase_required):
    dao = QuestDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.add_quest(_quest())
        dao.delete_quest(_QUEST_ID)
        assert dao.get_quest_by_id(_QUEST_ID) is None
    finally:
        _teardown(dao, period_dao, user_dao)
