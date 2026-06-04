from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import MagicMock

from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError
from services.parent.parent_service import ParentService


def _svc():
    svc = ParentService.__new__(ParentService)
    svc.parent_dao = MagicMock()
    svc.invite_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.user_dao = MagicMock()
    return svc


def _future_iso(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past_iso(hours=1):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()



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
    svc.student_dao.get_students_by_ids.return_value = [
        {"first_name": "Alice", "last_name": "A", "grade": "10", "email": "a@eduquestai.org"},
        {"first_name": "Bob", "last_name": "B", "grade": "11", "email": "b@eduquestai.org"},
    ]

    result = svc.get_linked_students("u1")

    assert len(result) == 2
    assert result[0]["first_name"] == "Alice"
    assert result[1]["first_name"] == "Bob"


@pytest.mark.unit
def test_get_linked_students_masks_internal_email():
    svc = _svc()
    svc.parent_dao.get_linked_student_ids.return_value = ["s1"]
    svc.student_dao.get_students_by_ids.return_value = [
        {
            "user_id": "s1",
            "first_name": "Child",
            "last_name": "",
            "grade": "5",
            "email": "child_abc123@internal.eduquestai.org",
            "interest": ["math"],
        }
    ]

    result = svc.get_linked_students("s1")

    assert result[0]["email"] == "", f"expected empty string, got {result[0]['email']!r}"


# ── accept_invite ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_accept_invite_invalid_code_raises():
    svc = _svc()
    svc.invite_dao.get_invite_by_code.return_value = None

    with pytest.raises(NotFoundError, match="Invite code not found"):
        svc.accept_invite("s1", "BADCODE1")


@pytest.mark.unit
def test_accept_invite_used_code_raises():
    svc = _svc()
    svc.invite_dao.get_invite_by_code.return_value = {
        "used": True,
        "expires_at": _future_iso(),
        "user_id": "parent-1",
    }

    with pytest.raises(ValidationError, match="already been used"):
        svc.accept_invite("s1", "USEDCODE")


@pytest.mark.unit
def test_accept_invite_expired_code_raises():
    svc = _svc()
    svc.invite_dao.get_invite_by_code.return_value = {
        "used": False,
        "expires_at": _past_iso(hours=2),
        "user_id": "parent-1",
    }

    with pytest.raises(ValidationError, match="expired"):
        svc.accept_invite("s1", "EXPCODE1")


@pytest.mark.unit
def test_accept_invite_timezone_naive_datetime_handled():
    svc = _svc()
    # expires_at without tzinfo — service must attach UTC and accept a future date
    naive_future = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
    svc.invite_dao.get_invite_by_code.return_value = {
        "used": False,
        "expires_at": naive_future,
        "user_id": "parent-1",
    }
    svc.parent_dao.get_parent_by_id.return_value = {
        "user_id": "parent-1",
        "linked_student_ids": [],
    }

    result = svc.accept_invite("s1", "TZCODE11")

    assert result["student_id"] == "s1"


@pytest.mark.unit
def test_accept_invite_missing_parent_id_raises():
    svc = _svc()
    svc.invite_dao.get_invite_by_code.return_value = {
        "used": False,
        "expires_at": _future_iso(),
        # "user_id" key intentionally absent
    }

    with pytest.raises(RuntimeError, match="missing user_id"):
        svc.accept_invite("s1", "NOPARENT")


@pytest.mark.unit
def test_accept_invite_parent_not_found_raises():
    svc = _svc()
    svc.invite_dao.get_invite_by_code.return_value = {
        "used": False,
        "expires_at": _future_iso(),
        "user_id": "ghost-parent",
    }
    svc.parent_dao.get_parent_by_id.return_value = None

    with pytest.raises(NotFoundError, match="Parent account not found"):
        svc.accept_invite("s1", "GPCODE11")


@pytest.mark.unit
def test_accept_invite_already_linked_returns_early():
    svc = _svc()
    svc.invite_dao.get_invite_by_code.return_value = {
        "used": False,
        "expires_at": _future_iso(),
        "user_id": "parent-1",
    }
    svc.parent_dao.get_parent_by_id.return_value = {
        "user_id": "parent-1",
        "linked_student_ids": ["s1"],  # already contains student
    }

    result = svc.accept_invite("s1", "LINKCODE")

    assert result.get("already_linked") is True
    svc.parent_dao.update_parent.assert_not_called()
    svc.invite_dao.mark_used.assert_not_called()


@pytest.mark.unit
def test_accept_invite_success():
    svc = _svc()
    svc.invite_dao.get_invite_by_code.return_value = {
        "used": False,
        "expires_at": _future_iso(),
        "user_id": "parent-1",
    }
    svc.parent_dao.get_parent_by_id.return_value = {
        "user_id": "parent-1",
        "linked_student_ids": ["existing-kid"],
    }

    result = svc.accept_invite("s1", "GOODCODE")

    # student appended and parent updated
    update_call_args = svc.parent_dao.update_parent.call_args
    updated_ids = update_call_args.args[1]["linked_student_ids"]
    assert "s1" in updated_ids
    assert "existing-kid" in updated_ids
    assert "vpc_verified_at" not in update_call_args.args[1]

    svc.invite_dao.mark_used.assert_called_once_with("GOODCODE")
    assert result["student_id"] == "s1"
    assert result["parent_id"] == "parent-1"


# ── create_student_profile ─────────────────────────────────────────────────


@pytest.mark.unit
def test_create_student_profile_blocked_until_authorization_flow_is_enabled():
    svc = _svc()
    svc.parent_dao.get_parent_by_id.return_value = {
        "user_id": "parent-1",
        "linked_student_ids": [],
    }

    with pytest.raises(ValidationError, match="temporarily unavailable"):
        svc.create_student_profile("parent-1", "Timmy", 6, [])
    svc.student_dao.add_student.assert_not_called()
