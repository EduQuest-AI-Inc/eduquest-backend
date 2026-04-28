import pytest
from unittest.mock import MagicMock

from services.parent.parent_service import ParentService


def _svc():
    svc = ParentService.__new__(ParentService)
    svc.parent_dao = MagicMock()
    svc.invite_dao = MagicMock()
    svc.student_dao = MagicMock()
    return svc



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


