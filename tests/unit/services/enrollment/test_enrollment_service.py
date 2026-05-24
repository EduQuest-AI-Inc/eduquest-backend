import pytest
from unittest.mock import MagicMock

from exceptions.not_found_error import NotFoundError
from exceptions.validation_error import ValidationError
from services.enrollment.enrollment_service import EnrollmentService


def _svc():
    svc = EnrollmentService.__new__(EnrollmentService)
    svc.enrollment_dao = MagicMock()
    svc.student_dao = MagicMock()
    svc.period_dao = MagicMock()
    svc.parent_dao = MagicMock()
    svc.user_dao = MagicMock()
    svc.quest_dao = MagicMock()
    svc.ltg_conversation_dao = MagicMock()
    svc.ltg_goal_dao = MagicMock()
    svc.conversation_dao = MagicMock()
    svc._admin_enrollment_dao = MagicMock()
    svc._admin_parent_dao = MagicMock()
    svc._admin_period_dao = MagicMock()
    svc._admin_user_dao = MagicMock()
    svc._admin_ltg_conversation_dao = MagicMock()
    svc._admin_conversation_dao = MagicMock()
    svc._admin_ltg_goal_dao = MagicMock()
    svc._admin_quest_dao = MagicMock()
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


# ─── validate_parent_enrollment_preconditions ─────────────────────────────────

@pytest.mark.unit
def test_validate_parent_enrollment_preconditions_passes():
    svc = _svc()
    svc.parent_dao.get_linked_student_ids.return_value = ["s1", "s2"]
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p-other"}]

    # Should not raise
    svc.validate_parent_enrollment_preconditions("parent-1", "s1", "p1")

    svc.parent_dao.get_linked_student_ids.assert_called_once_with("parent-1")
    svc.enrollment_dao.get_enrollments_by_student.assert_called_once_with("s1")


@pytest.mark.unit
def test_validate_parent_enrollment_preconditions_unlinked_raises():
    svc = _svc()
    svc.parent_dao.get_linked_student_ids.return_value = ["s2", "s3"]

    with pytest.raises(ValidationError, match="not linked"):
        svc.validate_parent_enrollment_preconditions("parent-1", "s1", "p1")


@pytest.mark.unit
def test_validate_parent_enrollment_preconditions_already_enrolled_raises():
    svc = _svc()
    svc.parent_dao.get_linked_student_ids.return_value = ["s1"]
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p1"}]

    with pytest.raises(ValidationError, match="already enrolled"):
        svc.validate_parent_enrollment_preconditions("parent-1", "s1", "p1")


# ── verify_period_id ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_verify_period_id_missing_raises():
    svc = _svc()

    with pytest.raises(ValidationError, match="Missing period ID"):
        svc.verify_period_id("s1", "")


@pytest.mark.unit
def test_verify_period_id_period_not_found_raises():
    svc = _svc()
    svc._admin_period_dao.get_period_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.verify_period_id("s1", "p1")


@pytest.mark.unit
def test_verify_period_id_owner_not_teacher_raises():
    svc = _svc()
    svc._admin_period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "o1", "status": "approved"}
    svc._admin_user_dao.get_by_id.return_value = {"user_id": "o1", "role": "parent"}

    with pytest.raises(NotFoundError):
        svc.verify_period_id("s1", "p1", allow_parent_period=False)


@pytest.mark.unit
def test_verify_period_id_not_approved_raises():
    svc = _svc()
    svc._admin_period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "o1", "status": "pending"}
    svc._admin_user_dao.get_by_id.return_value = {"user_id": "o1", "role": "teacher"}

    with pytest.raises(NotFoundError):
        svc.verify_period_id("s1", "p1")


@pytest.mark.unit
def test_verify_period_id_already_enrolled_raises():
    svc = _svc()
    svc._admin_period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "o1", "status": "approved"}
    svc._admin_user_dao.get_by_id.return_value = {"user_id": "o1", "role": "teacher"}
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p1"}]

    with pytest.raises(ValidationError, match="already enrolled"):
        svc.verify_period_id("s1", "p1")


@pytest.mark.unit
def test_verify_period_id_success_auto_enrolls():
    svc = _svc()
    period = {"period_id": "p1", "owner_id": "o1", "status": "approved"}
    svc._admin_period_dao.get_period_by_id.return_value = period
    svc._admin_user_dao.get_by_id.return_value = {"user_id": "o1", "role": "teacher"}
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = []

    result = svc.verify_period_id("s1", "p1")

    svc._admin_enrollment_dao.add_enrollment.assert_called_once()
    assert result == period


# ── unenroll_from_period ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_unenroll_missing_period_id_raises():
    svc = _svc()

    with pytest.raises(ValidationError, match="Missing period ID"):
        svc.unenroll_from_period("s1", "")


@pytest.mark.unit
def test_unenroll_student_not_found_raises():
    svc = _svc()
    svc.student_dao.get_student_by_id.return_value = None

    with pytest.raises(NotFoundError, match="Student not found"):
        svc.unenroll_from_period("s1", "p1")


@pytest.mark.unit
def test_unenroll_not_enrolled_raises():
    svc = _svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "other-p"}]

    with pytest.raises(ValidationError, match="not enrolled"):
        svc.unenroll_from_period("s1", "p1")


@pytest.mark.unit
def test_unenroll_swallows_enrollment_delete_error():
    svc = _svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p1"}]
    svc.enrollment_dao.delete_enrollment.side_effect = RuntimeError("DB error")
    svc.ltg_conversation_dao.delete_conversation.return_value = None
    svc.quest_dao.get_quests_by_student_and_period.return_value = []

    # Must not propagate despite delete_enrollment raising
    result = svc.unenroll_from_period("s1", "p1")

    assert result["period_id"] == "p1"


@pytest.mark.unit
def test_unenroll_cascades_ltg_and_quests():
    svc = _svc()
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = [
        {"period_id": "p1"},
        {"period_id": "p2"},
    ]
    # Deletes go through admin DAOs (FastAPI-only tables)
    svc._admin_ltg_conversation_dao.delete_conversation.return_value = "conv-1"
    svc.quest_dao.get_quests_by_student_and_period.return_value = [
        {"quest_id": "q1"},
        {"quest_id": "q2"},
    ]

    result = svc.unenroll_from_period("s1", "p1")

    svc._admin_ltg_goal_dao.delete.assert_called_once_with("s1", "p1")
    svc._admin_conversation_dao.delete_conversation.assert_called_once_with("conv-1")
    assert svc._admin_quest_dao.delete_quest.call_count == 2
    assert result["remaining_enrollments"] == ["p2"]


# ── get_my_periods ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_get_my_periods_maps_ltg():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_student.return_value = [
        {"period_id": "p1"},
        {"period_id": "p2"},
    ]
    svc.ltg_goal_dao.get_by_student.return_value = {"p1": "my goal"}
    svc.period_dao.get_periods_by_ids.return_value = [
        {"period_id": "p1", "name": "Algebra", "file_urls": [], "is_summer_quest": False},
        {"period_id": "p2", "name": "English", "file_urls": [], "is_summer_quest": False},
    ]

    result = svc.get_my_periods("s1")

    assert len(result) == 2
    p1 = next(r for r in result if r["period_id"] == "p1")
    p2 = next(r for r in result if r["period_id"] == "p2")
    assert p1["long_term_goal"] == "my goal"
    assert p2["long_term_goal"] is None


@pytest.mark.unit
def test_get_my_periods_skips_missing_period():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_student.return_value = [
        {"period_id": "p1"},
        {"period_id": "p-deleted"},
    ]
    svc.ltg_goal_dao.get_by_student.return_value = {}
    # p-deleted not returned by DAO (e.g. deleted from DB)
    svc.period_dao.get_periods_by_ids.return_value = [
        {"period_id": "p1", "name": "Math", "file_urls": [], "is_summer_quest": False},
    ]

    result = svc.get_my_periods("s1")

    assert len(result) == 1
    assert result[0]["period_id"] == "p1"


# ── has_teacher_access_to_student ─────────────────────────────────────────────


@pytest.mark.unit
def test_has_teacher_access_true():
    svc = _svc()
    svc._admin_period_dao.get_periods_by_owner_id.return_value = [
        {"period_id": "p1"},
        {"period_id": "p2"},
    ]
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p2"}]

    assert svc.has_teacher_access_to_student("teacher-1", "s1") is True


@pytest.mark.unit
def test_has_teacher_access_false():
    svc = _svc()
    svc._admin_period_dao.get_periods_by_owner_id.return_value = [{"period_id": "p1"}]
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p-other"}]

    assert svc.has_teacher_access_to_student("teacher-1", "s1") is False


# ── get_parent_periods_for_student ────────────────────────────────────────────


@pytest.mark.unit
def test_get_parent_periods_excludes_already_enrolled():
    svc = _svc()
    svc._admin_parent_dao.get_parents_by_student_id.return_value = [{"user_id": "parent-1"}]
    svc.enrollment_dao.get_enrollments_by_student.return_value = [{"period_id": "p1"}]
    svc._admin_period_dao.get_periods_by_owner_id.return_value = [
        {"period_id": "p1", "status": "approved"},
    ]

    result = svc.get_parent_periods_for_student("s1")

    assert result == []


@pytest.mark.unit
def test_get_parent_periods_includes_approved_only():
    svc = _svc()
    svc._admin_parent_dao.get_parents_by_student_id.return_value = [{"user_id": "parent-1"}]
    svc.enrollment_dao.get_enrollments_by_student.return_value = []
    svc._admin_period_dao.get_periods_by_owner_id.return_value = [
        {"period_id": "p1", "status": "approved"},
        {"period_id": "p2", "status": "pending"},
    ]

    result = svc.get_parent_periods_for_student("s1")

    assert len(result) == 1
    assert result[0]["period_id"] == "p1"


# ── cleanup_tutorial_periods ──────────────────────────────────────────────────

from services.enrollment.enrollment_service import TUTORIAL_PERIOD_ID


@pytest.mark.unit
def test_cleanup_tutorial_periods_removes_tutorial_when_enrolled():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_student.return_value = [
        {"period_id": TUTORIAL_PERIOD_ID},
        {"period_id": "real-period-1"},
    ]

    svc.cleanup_tutorial_periods("s1")

    svc.enrollment_dao.delete_enrollment.assert_called_once_with("s1", TUTORIAL_PERIOD_ID)


@pytest.mark.unit
def test_cleanup_tutorial_periods_noop_when_not_in_tutorial():
    svc = _svc()
    svc.enrollment_dao.get_enrollments_by_student.return_value = [
        {"period_id": "real-period-1"},
    ]

    svc.cleanup_tutorial_periods("s1")

    svc.enrollment_dao.delete_enrollment.assert_not_called()


@pytest.mark.unit
def test_verify_period_id_triggers_tutorial_cleanup_on_real_class():
    svc = _svc()
    period = {"period_id": "real-period-1", "owner_id": "o1", "status": "approved"}
    svc._admin_period_dao.get_period_by_id.return_value = period
    svc._admin_user_dao.get_by_id.return_value = {"user_id": "o1", "role": "teacher"}
    svc.student_dao.get_student_by_id.return_value = {"user_id": "s1"}
    svc.enrollment_dao.get_enrollments_by_student.return_value = [
        {"period_id": TUTORIAL_PERIOD_ID},
    ]

    svc.verify_period_id("s1", "real-period-1")

    svc.enrollment_dao.delete_enrollment.assert_called_with("s1", TUTORIAL_PERIOD_ID)
