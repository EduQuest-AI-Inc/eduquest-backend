"""
Integration tests for EnrollmentDAO.
Requires a period and student/user row to exist for FK constraints.
Uses PeriodDAO + UserDAO to set up prerequisites.
"""
import pytest
import uuid
from data_access.enrollment_dao import EnrollmentDAO
from data_access.period_dao import PeriodDAO
from data_access.user_dao import UserDAO
from models.enrollment import Enrollment
from models.period import Period

_PERIOD_ID = "test-step8-enroll-period"
_USER_ID = "test-step8-enroll-user"


def _setup(period_dao, user_dao):
    period_dao.add_period(Period(period_id=_PERIOD_ID, owner_id="test-owner", name="Enroll Test", vector_store_id="vs"))
    user_dao._insert({
        "user_id": _USER_ID, "first_name": "E", "last_name": "User",
        "email": "test-step8-enroll@example.com", "password": "pw", "role": "student",
    })


def _teardown(period_dao, user_dao, enrollment_dao):
    try:
        enrollment_dao.delete_enrollment(_USER_ID, _PERIOD_ID)
    except Exception:
        pass
    period_dao.delete_period(_PERIOD_ID)
    user_dao.delete(_USER_ID)


@pytest.mark.integration
def test_add_and_get_by_period(supabase_required):
    dao = EnrollmentDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        enrollment = Enrollment(user_id=_USER_ID, period_id=_PERIOD_ID, semester="Fall 2025")
        dao.add_enrollment(enrollment)
        results = dao.get_enrollments_by_period(_PERIOD_ID)
        assert any(r["user_id"] == _USER_ID for r in results)
    finally:
        _teardown(period_dao, user_dao, dao)


@pytest.mark.integration
def test_get_by_student(supabase_required):
    dao = EnrollmentDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        enrollment = Enrollment(user_id=_USER_ID, period_id=_PERIOD_ID, semester="Fall 2025")
        dao.add_enrollment(enrollment)
        results = dao.get_enrollments_by_student(_USER_ID)
        assert any(r["period_id"] == _PERIOD_ID for r in results)
    finally:
        _teardown(period_dao, user_dao, dao)


@pytest.mark.integration
def test_update_enrollment(supabase_required):
    dao = EnrollmentDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        enrollment = Enrollment(user_id=_USER_ID, period_id=_PERIOD_ID, semester="Fall 2025")
        dao.add_enrollment(enrollment)
        dao.update_enrollment(_USER_ID, _PERIOD_ID, {"semester": "Spring 2026"})
        results = dao.get_enrollments_by_period(_PERIOD_ID)
        row = next(r for r in results if r["user_id"] == _USER_ID)
        assert row["semester"] == "Spring 2026"
    finally:
        _teardown(period_dao, user_dao, dao)


@pytest.mark.integration
def test_delete_enrollment(supabase_required):
    dao = EnrollmentDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        enrollment = Enrollment(user_id=_USER_ID, period_id=_PERIOD_ID, semester="Fall 2025")
        dao.add_enrollment(enrollment)
        dao.delete_enrollment(_USER_ID, _PERIOD_ID)
        results = dao.get_enrollments_by_period(_PERIOD_ID)
        assert not any(r["user_id"] == _USER_ID for r in results)
    finally:
        _teardown(period_dao, user_dao, dao)
