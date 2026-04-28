"""Integration tests for LtgConversationDAO."""
import pytest
from data_access.ltg_conversation_dao import LtgConversationDAO

_CONV_ID = "test-integration-ltgconv-openai-id"


@pytest.mark.integration
def test_upsert_and_get_conversation_id(db_period, db_user):
    dao = LtgConversationDAO()
    dao.upsert_conversation(db_user.user_id, db_period.period_id, _CONV_ID)
    try:
        result = dao.get_conversation_id(db_user.user_id, db_period.period_id)
        assert result == _CONV_ID
    finally:
        dao.delete_conversation(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_get_and_update_last_response_id(db_period, db_user):
    dao = LtgConversationDAO()
    dao.upsert_conversation(db_user.user_id, db_period.period_id, _CONV_ID)
    try:
        dao.update_last_response_id(db_user.user_id, db_period.period_id, "resp-42")
        result = dao.get_last_response_id(db_user.user_id, db_period.period_id)
        assert result == "resp-42"
    finally:
        dao.delete_conversation(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_get_all_for_student(db_period, db_user):
    dao = LtgConversationDAO()
    dao.upsert_conversation(db_user.user_id, db_period.period_id, _CONV_ID)
    try:
        mapping = dao.get_all_for_student(db_user.user_id)
        assert db_period.period_id in mapping
        assert mapping[db_period.period_id] == _CONV_ID
    finally:
        dao.delete_conversation(db_user.user_id, db_period.period_id)


@pytest.mark.integration
def test_delete_conversation(db_period, db_user):
    dao = LtgConversationDAO()
    dao.upsert_conversation(db_user.user_id, db_period.period_id, _CONV_ID)
    returned_id = dao.delete_conversation(db_user.user_id, db_period.period_id)
    assert returned_id == _CONV_ID
    assert dao.get_conversation_id(db_user.user_id, db_period.period_id) is None


@pytest.mark.integration
def test_find_period_for_conversation(db_period, db_user):
    dao = LtgConversationDAO()
    dao.upsert_conversation(db_user.user_id, db_period.period_id, _CONV_ID)
    try:
        period_id = dao.find_period_for_conversation(db_user.user_id, _CONV_ID)
        assert period_id == db_period.period_id
    finally:
        dao.delete_conversation(db_user.user_id, db_period.period_id)
