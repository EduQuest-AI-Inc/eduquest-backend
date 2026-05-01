"""Integration tests for ConversationDAO."""
import pytest
from data_access.conversation_dao import ConversationDAO
from models.conversation import Conversation

_ID = "test-integration-conv-dao"


@pytest.mark.integration
def test_add_and_get_by_id(db_user):
    dao = ConversationDAO()
    conv = Conversation(conversation_id=_ID, user_id=db_user.user_id, conversation_type="profile")
    dao.add_conversation(conv)
    try:
        results = dao.get_conversations_by_id(_ID)
        assert any(r["conversation_id"] == _ID for r in results)
    finally:
        dao.delete_conversation(_ID)


@pytest.mark.integration
def test_get_conversation_by_id_user_type(db_user):
    dao = ConversationDAO()
    conv = Conversation(conversation_id=_ID, user_id=db_user.user_id, conversation_type="profile")
    dao.add_conversation(conv)
    try:
        result = dao.get_conversation_by_id_user_type(_ID, db_user.user_id, "profile")
        assert result is not None
        assert result["conversation_id"] == _ID
    finally:
        dao.delete_conversation(_ID)


@pytest.mark.integration
def test_update_conversation(db_user):
    dao = ConversationDAO()
    conv = Conversation(conversation_id=_ID, user_id=db_user.user_id, conversation_type="profile")
    dao.add_conversation(conv)
    try:
        dao.update_conversation(_ID, {"last_response_id": "resp-99"})
        results = dao.get_conversations_by_id(_ID)
        assert results[0]["last_response_id"] == "resp-99"
    finally:
        dao.delete_conversation(_ID)


@pytest.mark.integration
def test_delete_conversation(db_user):
    dao = ConversationDAO()
    conv = Conversation(conversation_id=_ID, user_id=db_user.user_id, conversation_type="profile")
    dao.add_conversation(conv)
    dao.delete_conversation(_ID)
    results = dao.get_conversations_by_id(_ID)
    assert results == []
