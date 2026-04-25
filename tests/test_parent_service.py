import pytest
from unittest.mock import MagicMock

from routes.parent.parent_service import ParentService


def _svc():
    svc = ParentService.__new__(ParentService)
    svc._period_mgmt = MagicMock()
    svc.parent_dao = MagicMock()
    svc.invite_dao = MagicMock()
    svc.student_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_create_period_delegates_to_period_mgmt():
    svc = _svc()
    svc._period_mgmt.create_period.return_value = {"period_id": "p1"}

    result = svc.create_period("Science", "u1", "vs1", [])

    svc._period_mgmt.create_period.assert_called_once_with("Science", "u1", "vs1", [])
    assert result == {"period_id": "p1"}


@pytest.mark.unit
def test_get_periods_by_parent_delegates():
    svc = _svc()
    svc._period_mgmt.get_periods_by_owner.return_value = [{"period_id": "p1"}]

    result = svc.get_periods_by_parent("u1")

    svc._period_mgmt.get_periods_by_owner.assert_called_once_with("u1")
    assert result == [{"period_id": "p1"}]


@pytest.mark.unit
def test_generate_invite_creates_token():
    svc = _svc()

    result = svc.generate_invite("u1")

    svc.invite_dao.create_invite.assert_called_once()
    assert "code" in result, f"expected 'code' key, got {result!r}"
    assert len(result["code"]) == 8


@pytest.mark.unit
def test_get_linked_students_empty():
    svc = _svc()
    svc.parent_dao.get_linked_student_ids.return_value = []

    result = svc.get_linked_students("u1")

    assert result == []


@pytest.mark.unit
def test_get_linked_students_success():
    svc = _svc()
    svc.parent_dao.get_linked_student_ids.return_value = ["s1", "s2"]
    svc.student_dao.get_student_by_id.side_effect = [
        {"first_name": "Alice", "last_name": "A", "grade": "10", "email": "a@a.com"},
        {"first_name": "Bob", "last_name": "B", "grade": "11", "email": "b@b.com"},
    ]

    result = svc.get_linked_students("u1")

    assert len(result) == 2
    assert result[0]["first_name"] == "Alice"
    assert result[1]["first_name"] == "Bob"


@pytest.mark.unit
def test_update_period_files_delegates():
    svc = _svc()

    svc.update_period_files("p1", ["url1"])

    svc._period_mgmt.update_file_urls.assert_called_once_with("p1", ["url1"])
