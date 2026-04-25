"""
Integration tests for PeriodScheduleDAO.
Requires a period FK row.
"""
import pytest
from data_access.period_schedule_dao import PeriodScheduleDAO
from data_access.period_dao import PeriodDAO
from models.period import Period
from models.period_schedule import PeriodSchedule

_PERIOD_ID = "test-step8-sched-period"


def _setup(period_dao):
    period_dao.add_period(Period(period_id=_PERIOD_ID, owner_id="owner", name="Schedule Test", vector_store_id="vs"))


def _teardown(dao, period_dao):
    try:
        dao.delete_period_schedule(_PERIOD_ID)
    except Exception:
        pass
    period_dao.delete_period(_PERIOD_ID)


@pytest.mark.integration
def test_add_and_get_by_period_id(supabase_required):
    dao = PeriodScheduleDAO()
    period_dao = PeriodDAO()
    _setup(period_dao)
    try:
        schedule = PeriodSchedule(period_id=_PERIOD_ID, schedule_json={"weeks": []}, quest_enabled_weeks=[1, 2])
        dao.add_period_schedule(schedule)
        result = dao.get_by_period_id(_PERIOD_ID)
        assert result is not None
        assert result.period_id == _PERIOD_ID
        assert result.quest_enabled_weeks == [1, 2]
    finally:
        _teardown(dao, period_dao)


@pytest.mark.integration
def test_update_period_schedule(supabase_required):
    dao = PeriodScheduleDAO()
    period_dao = PeriodDAO()
    _setup(period_dao)
    try:
        schedule = PeriodSchedule(period_id=_PERIOD_ID, schedule_json={}, quest_enabled_weeks=[])
        dao.add_period_schedule(schedule)
        dao.update_period_schedule(_PERIOD_ID, {"quest_enabled_weeks": [3, 4]})
        result = dao.get_by_period_id(_PERIOD_ID)
        assert result.quest_enabled_weeks == [3, 4]
    finally:
        _teardown(dao, period_dao)


@pytest.mark.integration
def test_delete_period_schedule(supabase_required):
    dao = PeriodScheduleDAO()
    period_dao = PeriodDAO()
    _setup(period_dao)
    try:
        schedule = PeriodSchedule(period_id=_PERIOD_ID, schedule_json={}, quest_enabled_weeks=[])
        dao.add_period_schedule(schedule)
        dao.delete_period_schedule(_PERIOD_ID)
        assert dao.get_by_period_id(_PERIOD_ID) is None
    finally:
        _teardown(dao, period_dao)
