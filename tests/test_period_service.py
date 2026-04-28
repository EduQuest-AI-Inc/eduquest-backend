import pytest
from unittest.mock import MagicMock, patch

from services.period.period_service import PeriodService


def _svc():
    svc = PeriodService.__new__(PeriodService)
    svc._enrollment = MagicMock()
    svc._quest = MagicMock()
    svc.period_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_get_my_periods_delegates_to_enrollment():
    svc = _svc()
    svc._enrollment.get_my_periods.return_value = [{"period_id": "p1"}]
    result = svc.get_my_periods("u1")
    svc._enrollment.get_my_periods.assert_called_once_with("u1")
    assert result == [{"period_id": "p1"}]


@pytest.mark.unit
def test_verify_period_id_delegates_to_enrollment():
    svc = _svc()
    svc.verify_period_id("u1", "p1")
    svc._enrollment.verify_period_id.assert_called_once_with("u1", "p1")


@pytest.mark.unit
def test_unenroll_from_period_delegates_to_enrollment():
    svc = _svc()
    svc.unenroll_from_period("u1", "p1")
    svc._enrollment.unenroll_from_period.assert_called_once_with("u1", "p1")


@pytest.mark.unit
def test_initiate_ltg_conversation_calls_run_initiate_ltg():
    with patch("services.period.period_service.run_initiate_ltg", return_value={"response": "LTG started"}) as mock_fn:
        svc = _svc()
        result = svc.initiate_ltg_conversation("u1", "p1")
    mock_fn.assert_called_once_with("u1", "p1")
    assert result == {"response": "LTG started"}


@pytest.mark.unit
def test_continue_ltg_conversation_calls_run_continue_ltg():
    with patch("services.period.period_service.run_continue_ltg", return_value={"response": "cont"}) as mock_fn:
        svc = _svc()
        result = svc.continue_ltg_conversation("u1", "ltg", "cid1", "Hello", period_id="p1")
    mock_fn.assert_called_once_with("u1", "ltg", "cid1", "Hello", "p1")
    assert result == {"response": "cont"}


@pytest.mark.unit
def test_continue_ltg_conversation_without_period_id():
    with patch("services.period.period_service.run_continue_ltg", return_value={}) as mock_fn:
        svc = _svc()
        svc.continue_ltg_conversation("u1", "ltg", "cid1", "Hi")
    mock_fn.assert_called_once_with("u1", "ltg", "cid1", "Hi", None)


@pytest.mark.unit
def test_start_homework_agent_delegates_to_quest():
    svc = _svc()
    svc._quest.start_homework_agent.return_value = {"quests": []}
    result = svc.start_homework_agent("u1", "p1")
    svc._quest.start_homework_agent.assert_called_once_with("u1", "p1")
    assert result == {"quests": []}


@pytest.mark.unit
def test_update_quests_arg_reordering():
    svc = _svc()
    svc.update_quests_with_recommended_change("tok", "p1", {"week": 2}, user_id="u1")
    svc._quest.update_quests_with_recommended_change.assert_called_once_with(
        "tok", "u1", "p1", {"week": 2}
    )


@pytest.mark.unit
def test_update_quests_arg_reordering_without_user_id():
    svc = _svc()
    svc.update_quests_with_recommended_change("tok", "p1", {"week": 1})
    svc._quest.update_quests_with_recommended_change.assert_called_once_with(
        "tok", None, "p1", {"week": 1}
    )


@pytest.mark.unit
def test_period_dao_exposed_on_svc():
    svc = PeriodService.__new__(PeriodService)
    svc._enrollment = MagicMock()
    svc._quest = MagicMock()
    svc.period_dao = svc._enrollment.period_dao
    assert svc.period_dao is svc._enrollment.period_dao
