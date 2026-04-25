"""
Integration tests for LtgConversationDAO.
Requires user + period FK rows.
"""
import pytest
from data_access.ltg_conversation_dao import LtgConversationDAO
from data_access.period_dao import PeriodDAO
from data_access.user_dao import UserDAO
from models.period import Period

_USER_ID = "test-step8-ltgconv-user"
_PERIOD_ID = "test-step8-ltgconv-period"
_CONV_ID = "test-step8-ltgconv-openai-id"


def _setup(period_dao, user_dao):
    period_dao.add_period(Period(period_id=_PERIOD_ID, owner_id="owner", name="LTG Test", vector_store_id="vs"))
    user_dao._insert({
        "user_id": _USER_ID, "first_name": "L", "last_name": "User",
        "email": "test-step8-ltgconv@example.com", "password": "pw", "role": "student",
    })


def _teardown(dao, period_dao, user_dao):
    try:
        dao.delete_conversation(_USER_ID, _PERIOD_ID)
    except Exception:
        pass
    period_dao.delete_period(_PERIOD_ID)
    user_dao.delete(_USER_ID)


@pytest.mark.integration
def test_upsert_and_get_conversation_id(supabase_required):
    dao = LtgConversationDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert_conversation(_USER_ID, _PERIOD_ID, _CONV_ID)
        result = dao.get_conversation_id(_USER_ID, _PERIOD_ID)
        assert result == _CONV_ID
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_get_and_update_last_response_id(supabase_required):
    dao = LtgConversationDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert_conversation(_USER_ID, _PERIOD_ID, _CONV_ID)
        dao.update_last_response_id(_USER_ID, _PERIOD_ID, "resp-42")
        result = dao.get_last_response_id(_USER_ID, _PERIOD_ID)
        assert result == "resp-42"
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_get_all_for_student(supabase_required):
    dao = LtgConversationDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert_conversation(_USER_ID, _PERIOD_ID, _CONV_ID)
        mapping = dao.get_all_for_student(_USER_ID)
        assert _PERIOD_ID in mapping
        assert mapping[_PERIOD_ID] == _CONV_ID
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_delete_conversation(supabase_required):
    dao = LtgConversationDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert_conversation(_USER_ID, _PERIOD_ID, _CONV_ID)
        returned_id = dao.delete_conversation(_USER_ID, _PERIOD_ID)
        assert returned_id == _CONV_ID
        assert dao.get_conversation_id(_USER_ID, _PERIOD_ID) is None
    finally:
        _teardown(dao, period_dao, user_dao)


@pytest.mark.integration
def test_find_period_for_conversation(supabase_required):
    dao = LtgConversationDAO()
    period_dao = PeriodDAO()
    user_dao = UserDAO()
    _setup(period_dao, user_dao)
    try:
        dao.upsert_conversation(_USER_ID, _PERIOD_ID, _CONV_ID)
        period_id = dao.find_period_for_conversation(_USER_ID, _CONV_ID)
        assert period_id == _PERIOD_ID
    finally:
        _teardown(dao, period_dao, user_dao)
