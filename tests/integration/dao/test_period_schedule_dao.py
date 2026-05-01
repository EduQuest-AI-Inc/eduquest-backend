"""Integration tests for PeriodScheduleDAO."""
import pytest
from data_access.period_schedule_dao import PeriodScheduleDAO
from models.period_schedule import PeriodSchedule


@pytest.mark.integration
def test_add_and_get_by_period_id(db_period):
    dao = PeriodScheduleDAO()
    schedule = PeriodSchedule(period_id=db_period.period_id, schedule_json={"weeks": []}, quest_enabled_weeks=[1, 2])
    dao.add_period_schedule(schedule)
    try:
        result = dao.get_by_period_id(db_period.period_id)
        assert result is not None
        assert result.period_id == db_period.period_id
        assert result.quest_enabled_weeks == [1, 2]
    finally:
        dao.delete_period_schedule(db_period.period_id)


@pytest.mark.integration
def test_update_period_schedule(db_period):
    dao = PeriodScheduleDAO()
    schedule = PeriodSchedule(period_id=db_period.period_id, schedule_json={}, quest_enabled_weeks=[])
    dao.add_period_schedule(schedule)
    try:
        dao.update_period_schedule(db_period.period_id, {"quest_enabled_weeks": [3, 4]})
        result = dao.get_by_period_id(db_period.period_id)
        assert result.quest_enabled_weeks == [3, 4]
    finally:
        dao.delete_period_schedule(db_period.period_id)


@pytest.mark.integration
def test_delete_period_schedule(db_period):
    dao = PeriodScheduleDAO()
    schedule = PeriodSchedule(period_id=db_period.period_id, schedule_json={}, quest_enabled_weeks=[])
    dao.add_period_schedule(schedule)
    dao.delete_period_schedule(db_period.period_id)
    assert dao.get_by_period_id(db_period.period_id) is None
