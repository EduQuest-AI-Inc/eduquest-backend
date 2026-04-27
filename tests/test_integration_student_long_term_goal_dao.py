"""
Integration tests for StudentLongTermGoalDAO.
Requires user + period FK rows.
"""
import pytest
from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
from data_access.period_dao import PeriodDAO
from data_access.user_dao import UserDAO
from models.period import Period
from models.user import User

_USER_ID = "test-step8-ltg-user"
_PERIOD_ID = "test-step8-ltg-period"
_PERIOD_ID2 = "test-step8-ltg-period2"


def _setup(period_dao, user_dao):
    period_dao.add_period(Period(period_id=_PERIOD_ID, owner_id="owner", name="LTG Goal Test", vector_store_id="vs"))
    user_dao.add_user(User(
        user_id=_USER_ID, first_name="G", last_name="User",
        email="test-step8-ltg@example.com", password="pw", role="student",
    ))


def _teardown(dao, period_dao, user_dao):
    try:
        dao.delete(_USER_ID, _PERIOD_ID)
    except Exception:
        pass
    try:
        dao.delete(_USER_ID, _PERIOD_ID2)
    except Exception:
        pass
    try:
        period_dao.delete_period(_PERIOD_ID2)
    except Exception:
        pass
    period_dao.delete_period(_PERIOD_ID)
    user_dao.delete(_USER_ID)


@pytest.mark.integration
def test_upsert_and_get_goal(supabase_required):
    dao = StudentLongTermGoalDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert(_USER_ID, _PERIOD_ID, "Become a doctor")
        result = dao.get_by_student_and_period(_USER_ID, _PERIOD_ID)
        assert result == "Become a doctor"
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_update_goal(supabase_required):
    dao = StudentLongTermGoalDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert(_USER_ID, _PERIOD_ID, "Become a doctor")
        dao.upsert(_USER_ID, _PERIOD_ID, "Become an engineer")
        result = dao.get_by_student_and_period(_USER_ID, _PERIOD_ID)
        assert result == "Become an engineer"
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_get_all_for_student(supabase_required):
    dao = StudentLongTermGoalDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    period_dao.add_period(Period(period_id=_PERIOD_ID2, owner_id="owner", name="LTG Goal Test 2", vector_store_id="vs2"))
    try:
        dao.upsert(_USER_ID, _PERIOD_ID, "Goal 1")
        dao.upsert(_USER_ID, _PERIOD_ID2, "Goal 2")
        mapping = dao.get_by_student(_USER_ID)
        assert mapping.get(_PERIOD_ID) == "Goal 1"
        assert mapping.get(_PERIOD_ID2) == "Goal 2"
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_delete_goal(supabase_required):
    dao = StudentLongTermGoalDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert(_USER_ID, _PERIOD_ID, "Delete me")
        dao.delete(_USER_ID, _PERIOD_ID)
        result = dao.get_by_student_and_period(_USER_ID, _PERIOD_ID)
        assert result is None
    finally:
        _teardown(dao, period_dao, user_dao)
