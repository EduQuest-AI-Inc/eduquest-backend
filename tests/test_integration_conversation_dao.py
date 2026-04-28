"""
Integration tests for ConversationDAO.
Uses UserDAO to create the prerequisite user row.
"""
import pytest
from data_access.conversation_dao import ConversationDAO
from data_access.user_dao import UserDAO
from models.conversation import Conversation

_ID = "test-integration-conv-dao"
_USER_ID = "test-integration-conv-user"


def _setup(user_dao):
    user_dao._insert({
        "user_id": _USER_ID, "first_name": "C", "last_name": "User",
        "email": "test-integration-conv@example.com", "password": "pw", "role": "student",
    })


def _teardown(dao, user_dao):
    try:
        dao.delete_conversation(_ID)
    except Exception:
        pass
    user_dao.delete(_USER_ID)


@pytest.mark.integration
def test_add_and_get_by_id(supabase_required):
    dao = ConversationDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        conv = Conversation(conversation_id=_ID, user_id=_USER_ID, conversation_type="profile")
        dao.add_conversation(conv)
        results = dao.get_conversations_by_id(_ID)
        assert any(r["conversation_id"] == _ID for r in results)
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_get_conversation_by_id_user_type(supabase_required):
    dao = ConversationDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        conv = Conversation(conversation_id=_ID, user_id=_USER_ID, conversation_type="profile")
        dao.add_conversation(conv)
        result = dao.get_conversation_by_id_user_type(_ID, _USER_ID, "profile")
        assert result is not None
        assert result["conversation_id"] == _ID
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_update_conversation(supabase_required):
    dao = ConversationDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        conv = Conversation(conversation_id=_ID, user_id=_USER_ID, conversation_type="profile")
        dao.add_conversation(conv)
        dao.update_conversation(_ID, {"last_response_id": "resp-99"})
        results = dao.get_conversations_by_id(_ID)
        assert results[0]["last_response_id"] == "resp-99"
    finally:
        _teardown(dao, user_dao)


@pytest.mark.integration
def test_delete_conversation(supabase_required):
    dao = ConversationDAO()
    user_dao = UserDAO()
    _setup(user_dao)
    try:
        conv = Conversation(conversation_id=_ID, user_id=_USER_ID, conversation_type="profile")
        dao.add_conversation(conv)
        dao.delete_conversation(_ID)
        results = dao.get_conversations_by_id(_ID)
        assert results == []
    finally:
        _teardown(dao, user_dao)
