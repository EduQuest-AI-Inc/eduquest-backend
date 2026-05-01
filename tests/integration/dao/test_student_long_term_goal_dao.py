"""Integration tests for StudentLongTermGoalDAO."""
import pytest
from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
from data_access.period_dao import PeriodDAO
from models.period import Period

_PERIOD_ID2 = "test-integration-ltg-period2"


@pytest.mark.integration
def test_upsert_and_get_goal(db_period, db_user):
    dao = StudentLongTermGoalDAO()
    dao.upsert(db_user.user_id, db_period.period_id, "Become a doctor")
    try:
        result = dao.get_by_student_and_period(db_user.user_id, db_period.period_id)
        assert result == "Become a doctor"
    finally:
        dao.delete(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_update_goal(db_period, db_user):
    dao = StudentLongTermGoalDAO()
    dao.upsert(db_user.user_id, db_period.period_id, "Become a doctor")
    try:
        dao.upsert(db_user.user_id, db_period.period_id, "Become an engineer")
        result = dao.get_by_student_and_period(db_user.user_id, db_period.period_id)
        assert result == "Become an engineer"
    finally:
        dao.delete(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_get_all_for_student(db_period, db_user):
    dao = StudentLongTermGoalDAO()
    period_dao = PeriodDAO()
    period_dao.add_period(Period(period_id=_PERIOD_ID2, owner_id="owner", name="LTG Goal Test 2", vector_store_id="vs2"))
    try:
        dao.upsert(db_user.user_id, db_period.period_id, "Goal 1")
        dao.upsert(db_user.user_id, _PERIOD_ID2, "Goal 2")
        mapping = dao.get_by_student(db_user.user_id)
        assert mapping.get(db_period.period_id) == "Goal 1"
        assert mapping.get(_PERIOD_ID2) == "Goal 2"
    finally:
        try:
            dao.delete(db_user.user_id, db_period.period_id)
        except Exception:
            pass
        try:
            dao.delete(db_user.user_id, _PERIOD_ID2)
        except Exception:
            pass
        period_dao.delete_period(_PERIOD_ID2)


@pytest.mark.integration
def test_delete_goal(db_period, db_user):
    dao = StudentLongTermGoalDAO()
    dao.upsert(db_user.user_id, db_period.period_id, "Delete me")
    dao.delete(db_user.user_id, db_period.period_id)
    result = dao.get_by_student_and_period(db_user.user_id, db_period.period_id)
    assert result is None
