import pytest
from unittest.mock import MagicMock

from services.period.period_schedule_service import PeriodScheduleService


def _svc():
    svc = PeriodScheduleService.__new__(PeriodScheduleService)
    svc.period_dao = MagicMock()
    svc.period_schedule_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_verify_period_ownership_not_found():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(ValueError, match="not found"):
        svc._verify_period_ownership("p1", "u1")


@pytest.mark.unit
def test_verify_period_ownership_wrong_owner():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "other"}

    with pytest.raises(PermissionError):
        svc._verify_period_ownership("p1", "u1")


@pytest.mark.unit
def test_verify_period_ownership_success():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "u1"}

    result = svc._verify_period_ownership("p1", "u1")

    assert result["period_id"] == "p1"


@pytest.mark.unit
def test_get_schedule_success():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "u1"}
    schedule_obj = MagicMock()
    schedule_obj.schedule_json = {"weeks": []}
    schedule_obj.quest_enabled_weeks = [1, 2]
    schedule_obj.last_updated_at = "2024-01-01"
    svc.period_schedule_dao.get_by_period_id.return_value = schedule_obj

    result = svc.get_schedule("p1", "u1")

    assert result is not None
    assert result["quest_enabled_weeks"] == [1, 2]


@pytest.mark.unit
def test_get_schedule_no_schedule():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "u1"}
    svc.period_schedule_dao.get_by_period_id.return_value = None

    result = svc.get_schedule("p1", "u1")

    assert result is None


@pytest.mark.unit
def test_save_schedule_and_quest_weeks_checks_ownership_first():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None  # triggers ValueError

    with pytest.raises(ValueError):
        svc.save_schedule_and_quest_weeks("p1", "u1", {}, [])

    svc.period_schedule_dao.update_period_schedule.assert_not_called()


@pytest.mark.unit
def test_save_schedule_and_quest_weeks_normalizes_weeks(monkeypatch):
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {
        "period_id": "p1", "owner_id": "u1", "vector_store_id": "vs1"
    }
    existing = MagicMock()
    existing.schedule_openai_file_id = None
    svc.period_schedule_dao.get_by_period_id.return_value = existing

    monkeypatch.setattr(svc, "_upload_schedule_to_vector_store", lambda *_: "file-new")

    result = svc.save_schedule_and_quest_weeks("p1", "u1", {}, [3, 1, 2])

    call_kwargs = svc.period_schedule_dao.update_period_schedule.call_args[0][1]
    assert call_kwargs["quest_enabled_weeks"] == [1, 2, 3]
    assert result["quest_enabled_weeks"] == [1, 2, 3]
