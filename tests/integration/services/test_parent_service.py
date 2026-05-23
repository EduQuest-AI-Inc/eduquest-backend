"""
Integration tests: ParentService invite flow.

Verifies that generate_invite inserts into parent_invite (FastAPI-only) and
accept_invite updates parent_invite + parent — all mutations that require the
admin client. Reverting to a user JWT DAO causes 42501 RLS violations.
"""
import pytest


def _delete_invites(parent_id: str) -> None:
    from data_access.parent_invite_dao import ParentInviteDAO
    try:
        ParentInviteDAO()._delete({'user_id': parent_id})
    except Exception:
        pass


@pytest.mark.integration
def test_generate_invite_creates_row(supabase_required, db_parent):
    from data_access.parent_invite_dao import ParentInviteDAO
    from services.parent.parent_service import ParentService

    svc = ParentService()
    result = svc.generate_invite(db_parent.user_id)
    code = result["code"]
    try:
        row = ParentInviteDAO().get_invite_by_code(code)
        assert row is not None
        assert row["user_id"] == db_parent.user_id
        assert row["used"] is False
    finally:
        _delete_invites(db_parent.user_id)


@pytest.mark.integration
def test_accept_invite_links_student_and_marks_used(
    supabase_required, db_parent, db_student
):
    from data_access.parent_invite_dao import ParentInviteDAO
    from data_access.parent_dao import ParentDAO
    from services.parent.parent_service import ParentService

    svc = ParentService()
    result = svc.generate_invite(db_parent.user_id)
    code = result["code"]
    try:
        link_result = svc.accept_invite(db_student.user_id, code)

        assert link_result.get("student_id") == db_student.user_id
        assert link_result.get("parent_id") == db_parent.user_id

        invite_row = ParentInviteDAO().get_invite_by_code(code)
        assert invite_row["used"] is True

        parent_row = ParentDAO().get_parent_by_id(db_parent.user_id)
        assert db_student.user_id in parent_row["linked_student_ids"]
    finally:
        _delete_invites(db_parent.user_id)
        ParentDAO().update_parent(db_parent.user_id, {"linked_student_ids": []})
