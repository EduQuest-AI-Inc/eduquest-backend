"""
Integration test: unenroll_from_period cascade deletes.

Verifies that unenroll_from_period successfully deletes rows from ltg_conversation,
conversation, student_long_term_goal, and quest — all FastAPI-only tables that require
the admin client. If the service reverts to a user JWT DAO, these deletes fail with
a PostgREST 42501 RLS violation.
"""
import pytest

_QUEST_ID = "test-integration-unenroll-quest-1"
_CONV_ID = "test-integration-unenroll-conv-1"


def _seed(user_id: str, period_id: str) -> None:
    """Insert one row in each FastAPI-only table that unenroll should cascade-delete."""
    from data_access.ltg_conversation_dao import LtgConversationDAO
    from data_access.conversation_dao import ConversationDAO
    from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
    from data_access.quest_dao import QuestDAO
    from models.conversation import Conversation
    from models.quest import Quest

    LtgConversationDAO().upsert_conversation(user_id, period_id, _CONV_ID)
    ConversationDAO().add_conversation(
        Conversation(conversation_id=_CONV_ID, user_id=user_id, conversation_type="ltg")
    )
    StudentLongTermGoalDAO().upsert(user_id, period_id, "Test goal for unenroll cascade")
    QuestDAO().add_quest(Quest(
        quest_id=_QUEST_ID,
        user_id=user_id,
        period_id=period_id,
        description="Test quest",
        skills="test-skill",
        week=1,
        rubric={"Criteria": {}},
    ))


def _cleanup(user_id: str, period_id: str) -> None:
    """Best-effort cleanup in case the test fails before unenroll runs."""
    from data_access.ltg_conversation_dao import LtgConversationDAO
    from data_access.conversation_dao import ConversationDAO
    from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
    from data_access.quest_dao import QuestDAO
    from data_access.enrollment_dao import EnrollmentDAO

    try:
        LtgConversationDAO()._delete({'user_id': user_id, 'period_id': period_id})
    except Exception:
        pass
    try:
        ConversationDAO()._delete({'conversation_id': _CONV_ID})
    except Exception:
        pass
    try:
        StudentLongTermGoalDAO()._delete({'user_id': user_id, 'period_id': period_id})
    except Exception:
        pass
    try:
        QuestDAO()._delete({'quest_id': _QUEST_ID})
    except Exception:
        pass
    try:
        EnrollmentDAO().delete_enrollment(user_id, period_id)
    except Exception:
        pass


@pytest.mark.integration
def test_unenroll_cascade_deletes_all_fastapi_only_rows(
    supabase_required, db_student, db_period, db_enrollment
):
    from data_access.ltg_conversation_dao import LtgConversationDAO
    from data_access.conversation_dao import ConversationDAO
    from data_access.student_long_term_goal_dao import StudentLongTermGoalDAO
    from data_access.quest_dao import QuestDAO
    from services.enrollment.enrollment_service import EnrollmentService

    user_id = db_student.user_id
    period_id = db_period.period_id

    _seed(user_id, period_id)
    try:
        svc = EnrollmentService()
        result = svc.unenroll_from_period(user_id, period_id)

        assert result["period_id"] == period_id

        assert LtgConversationDAO().get_conversation_id(user_id, period_id) is None
        assert ConversationDAO().get_conversations_by_id(_CONV_ID) == []
        assert StudentLongTermGoalDAO().get_by_student_and_period(user_id, period_id) is None
        assert QuestDAO().get_quest_by_id(_QUEST_ID) is None
    finally:
        _cleanup(user_id, period_id)
