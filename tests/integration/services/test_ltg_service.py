"""
Integration test: LTGOrchestrationService.initiate() creates ltg_conversation row.

Verifies that initiate() upserts into ltg_conversation (FastAPI-only table) without
a 42501 RLS violation. MockBotProvider is injected to avoid real OpenAI calls while
still exercising the full service path including the DB write.
"""
import pytest


@pytest.mark.integration
def test_initiate_creates_ltg_conversation_row(
    supabase_required, db_student, db_period, db_enrollment
):
    from bots.provider import MockBotProvider
    from data_access.ltg_conversation_dao import LtgConversationDAO
    from services.conversation.ltg_service import LTGOrchestrationService

    user_id = db_student.user_id
    period_id = db_period.period_id

    svc = LTGOrchestrationService(bot_provider=MockBotProvider())
    try:
        result = svc.initiate(user_id, period_id)

        assert result is not None
        assert result.get("conversation_id") is not None

        conv_id = LtgConversationDAO().get_conversation_id(user_id, period_id)
        assert conv_id is not None
    finally:
        try:
            LtgConversationDAO()._delete({'user_id': user_id, 'period_id': period_id})
        except Exception:
            pass
