import pytest
from unittest.mock import MagicMock

from routes.teacher.teacher_service import TeacherService


def _svc():
    svc = TeacherService.__new__(TeacherService)
    svc._period_mgmt = MagicMock()
    return svc


@pytest.mark.unit
def test_create_period_delegates():
    svc = _svc()
    svc._period_mgmt.create_period.return_value = {"period_id": "p1"}

    result = svc.create_period("Math", "u1", "vs1", [], canvas_course_id="cc1", canvas_course_name="CM")

    svc._period_mgmt.create_period.assert_called_once_with(
        "Math", "u1", "vs1", [], canvas_course_id="cc1", canvas_course_name="CM"
    )
    assert result == {"period_id": "p1"}


@pytest.mark.unit
def test_get_periods_by_teacher_delegates():
    svc = _svc()
    svc._period_mgmt.get_periods_by_owner.return_value = [{"period_id": "p1"}]

    result = svc.get_periods_by_teacher("u1")

    svc._period_mgmt.get_periods_by_owner.assert_called_once_with("u1")
    assert result == [{"period_id": "p1"}]


@pytest.mark.unit
def test_get_period_by_id_delegates():
    svc = _svc()
    svc._period_mgmt.get_period_by_id.return_value = {"period_id": "p1"}

    result = svc.get_period_by_id("p1")

    svc._period_mgmt.get_period_by_id.assert_called_once_with("p1")
    assert result == {"period_id": "p1"}


@pytest.mark.unit
def test_update_period_files_delegates():
    svc = _svc()

    svc.update_period_files("p1", ["url1"])

    svc._period_mgmt.update_file_urls.assert_called_once_with("p1", ["url1"])


@pytest.mark.unit
def test_get_vector_store_id_delegates():
    svc = _svc()
    svc._period_mgmt.get_vector_store_id.return_value = "vs99"

    result = svc.get_vector_store_id_for_period("p1")

    svc._period_mgmt.get_vector_store_id.assert_called_once_with("p1")
    assert result == "vs99"
