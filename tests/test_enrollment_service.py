import pytest
from unittest.mock import MagicMock

from routes.enrollment.enrollment_service import EnrollmentService


def _svc():
    svc = EnrollmentService.__new__(EnrollmentService)
    svc.enrollment_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.period_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_enroll_student_success():
    svc = _svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}

    result = svc.enroll_student("s1", "p1")

    svc.enrollment_dao.add_enrollment.assert_called_once()
    assert "message" in result, f"expected 'message' key, got {result!r}"


@pytest.mark.unit
def test_enroll_student_not_found():
    svc = _svc()
    svc.student_dao.get_student_by_id.return_value = None

    with pytest.raises(Exception, match="s1"):
        svc.enroll_student("s1", "p1")


@pytest.mark.unit
def test_enroll_student_period_not_found():
    svc = _svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(Exception, match="p1"):
        svc.enroll_student("s1", "p1")


@pytest.mark.unit
def test_get_enrollments_for_period_with_files():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": "s1"}]
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "file_urls": ["url1"]}

    result = svc.get_enrollments_for_period("p1")

    assert result["file_urls"] == ["url1"], f"expected ['url1'], got {result['file_urls']!r}"


@pytest.mark.unit
def test_get_enrollments_for_period_no_period():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = []
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.get_enrollments_for_period("p1")

    assert result["file_urls"] == [], f"expected [], got {result['file_urls']!r}"


@pytest.mark.unit
def test_get_student_profile_not_enrolled():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": "other"}]

    result = svc.get_student_profile("p1", "s1")

    assert result is None


@pytest.mark.unit
def test_get_student_profile_student_not_found():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": "s1"}]
    svc.student_dao.get_student_by_id.return_value = None

    result = svc.get_student_profile("p1", "s1")

    assert result is None


@pytest.mark.unit
def test_get_student_profile_success():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_period.return_value = [{"user_id": "s1"}]
    svc.student_dao.get_student_by_id.return_value = {
        "user_id": "s1",
        "interest": "math",
        "strength": "algebra",
        "weakness": "geometry",
        "learning_style": "visual",
    }

    result = svc.get_student_profile("p1", "s1")

    assert result is not None
    assert result["interest"] == "math"
    assert result["strength"] == "algebra"
    assert result["weakness"] == "geometry"
    assert result["learning_style"] == "visual"


@pytest.mark.unit
def test_delete_enrollment():
    svc = _svc()

    result = svc.delete_enrollment("s1", "p1")

    svc.enrollment_dao.delete_enrollment.assert_called_once_with("s1", "p1")
    assert "message" in result, f"expected 'message' key, got {result!r}"
