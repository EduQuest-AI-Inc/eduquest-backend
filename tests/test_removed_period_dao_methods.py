import pytest
from data_access.period_dao import PeriodDAO


@pytest.mark.unit
def test_get_periods_by_teacher_id_removed():
    dao = PeriodDAO.__new__(PeriodDAO)
    assert not hasattr(dao, 'get_periods_by_teacher_id'), \
        "get_periods_by_teacher_id was removed in step 4 — do not re-add it"


@pytest.mark.unit
def test_get_periods_by_parent_id_removed():
    dao = PeriodDAO.__new__(PeriodDAO)
    assert not hasattr(dao, 'get_periods_by_parent_id'), \
        "get_periods_by_parent_id was removed in step 4 — do not re-add it"
