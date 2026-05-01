"""Integration tests for EnrollmentDAO."""
import pytest
from data_access.enrollment_dao import EnrollmentDAO
from models.enrollment import Enrollment


@pytest.mark.integration
def test_add_and_get_by_period(db_period, db_user):
    dao = EnrollmentDAO()
    enrollment = Enrollment(user_id=db_user.user_id, period_id=db_period.period_id, semester="Fall 2025")
    dao.add_enrollment(enrollment)
    try:
        results = dao.get_enrollments_by_period(db_period.period_id)
        assert any(r["user_id"] == db_user.user_id for r in results)
    finally:
        dao.delete_enrollment(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_get_by_student(db_period, db_user):
    dao = EnrollmentDAO()
    enrollment = Enrollment(user_id=db_user.user_id, period_id=db_period.period_id, semester="Fall 2025")
    dao.add_enrollment(enrollment)
    try:
        results = dao.get_enrollments_by_student(db_user.user_id)
        assert any(r["period_id"] == db_period.period_id for r in results)
    finally:
        dao.delete_enrollment(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_update_enrollment(db_period, db_user):
    dao = EnrollmentDAO()
    enrollment = Enrollment(user_id=db_user.user_id, period_id=db_period.period_id, semester="Fall 2025")
    dao.add_enrollment(enrollment)
    try:
        dao.update_enrollment(db_user.user_id, db_period.period_id, {"semester": "Spring 2026"})
        results = dao.get_enrollments_by_period(db_period.period_id)
        row = next(r for r in results if r["user_id"] == db_user.user_id)
        assert row["semester"] == "Spring 2026"
    finally:
        dao.delete_enrollment(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_delete_enrollment(db_period, db_user):
    dao = EnrollmentDAO()
    enrollment = Enrollment(user_id=db_user.user_id, period_id=db_period.period_id, semester="Fall 2025")
    dao.add_enrollment(enrollment)
    dao.delete_enrollment(db_user.user_id, db_period.period_id)
    results = dao.get_enrollments_by_period(db_period.period_id)
    assert not any(r["user_id"] == db_user.user_id for r in results)
