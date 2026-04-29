import pytest
from unittest.mock import MagicMock

from services.waitlist.WaitlistService import WaitlistService


def _svc():
    return WaitlistService(dao=MagicMock(), teacher_dao=MagicMock())


@pytest.mark.unit
def test_join_teacher_not_found():
    svc = _svc()
    svc.teacher_dao.get_teacher_by_id.return_value = None

    with pytest.raises(ValueError, match="Teacher not found"):
        svc.join("u1")


@pytest.mark.unit
def test_join_already_approved():
    svc = _svc()
    svc.teacher_dao.get_teacher_by_id.return_value = {
        "user_id": "u1", "email": "t@eduquestai.org", "pilot_approved": True
    }

    result = svc.join("u1")

    assert result.get("already_approved") is True
    svc.dao.join_waitlist.assert_not_called()


@pytest.mark.unit
def test_join_success_no_referral():
    svc = _svc()
    svc.teacher_dao.get_teacher_by_id.return_value = {
        "user_id": "u1", "email": "t@eduquestai.org", "pilot_approved": False
    }
    svc.dao.join_waitlist.return_value = {
        "position": 5, "referralCode": "ABC123", "status": "waiting", "joinedAt": "now", "referredBy": None
    }

    result = svc.join("u1")

    svc.dao.join_waitlist.assert_called_once()
    assert result["success"] is True


@pytest.mark.unit
def test_join_valid_referral_accepted():
    svc = _svc()
    svc.teacher_dao.get_teacher_by_id.return_value = {
        "user_id": "u1", "email": "t@eduquestai.org", "pilot_approved": False
    }
    svc.dao.validate_referral_code.return_value = {"valid": True, "referrer_id": "other_teacher"}
    svc.dao.join_waitlist.return_value = {
        "position": 3, "referralCode": "XYZ", "status": "waiting", "joinedAt": "now", "referredBy": "other_teacher"
    }

    svc.join("u1", referral_code="REFCODE")

    args, kwargs = svc.dao.join_waitlist.call_args
    # referred_by should be passed and equal to "other_teacher"
    assert "other_teacher" in args or kwargs.get("referred_by") == "other_teacher"


@pytest.mark.unit
def test_join_self_referral_ignored():
    svc = _svc()
    svc.teacher_dao.get_teacher_by_id.return_value = {
        "user_id": "u1", "email": "t@eduquestai.org", "pilot_approved": False
    }
    svc.dao.validate_referral_code.return_value = {"valid": True, "referrer_id": "u1"}
    svc.dao.join_waitlist.return_value = {
        "position": 1, "referralCode": "CODE", "status": "waiting", "joinedAt": "now", "referredBy": None
    }

    svc.join("u1", referral_code="SELFREF")

    args, kwargs = svc.dao.join_waitlist.call_args
    # referred_by should be None (self-referral ignored)
    called_referred_by = args[2] if len(args) > 2 else kwargs.get("referred_by")
    assert called_referred_by is None, f"expected None for self-referral, got {called_referred_by!r}"


@pytest.mark.unit
def test_get_status_approved_teacher():
    svc = _svc()
    svc.teacher_dao.get_teacher_by_id.return_value = {"pilot_approved": True}

    result = svc.get_status("u1")

    assert result["approved"] is True
    svc.dao.get_status.assert_not_called()


@pytest.mark.unit
def test_get_status_delegates_to_dao():
    svc = _svc()
    svc.teacher_dao.get_teacher_by_id.return_value = {"pilot_approved": False}
    svc.dao.get_status.return_value = {"on_waitlist": True, "position": 7}

    result = svc.get_status("u1")

    svc.dao.get_status.assert_called_once_with("u1")
    assert result["on_waitlist"] is True


@pytest.mark.unit
def test_approve_both_succeed():
    svc = _svc()
    svc.dao.approve_user.return_value = True

    result = svc.approve("u1")

    assert result["success"] is True


@pytest.mark.unit
def test_approve_teacher_update_fails():
    svc = _svc()
    svc.dao.approve_user.return_value = True
    svc.teacher_dao.update_teacher.side_effect = Exception("DB error")

    result = svc.approve("u1")

    assert result["teacher_updated"] is False
    assert result["success"] is False
