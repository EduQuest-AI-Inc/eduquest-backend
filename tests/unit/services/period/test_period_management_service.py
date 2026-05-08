import pytest
from unittest.mock import MagicMock

from services.period.period_management_service import PeriodManagementService


def _svc():
    svc = PeriodManagementService.__new__(PeriodManagementService)
    svc.period_dao = MagicMock()
    return svc


@pytest.mark.unit
def test_generate_period_id_no_collision():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.generate_period_id("Math 101")

    assert result, "expected a non-empty period ID"
    assert "-" in result


@pytest.mark.unit
def test_create_period_with_collision():
    """create_period retries when the generated ID already exists."""
    svc = _svc()
    # First get_period_by_id call returns a hit (ID taken); second returns None (free).
    svc.period_dao.get_period_by_id.side_effect = [{"period_id": "taken"}, None]

    result = svc.create_period("Math 101", "u1", "vs1", [])

    assert result
    assert svc.period_dao.get_period_by_id.call_count == 2


@pytest.mark.unit
def test_create_period_success():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.create_period(
        course="Physics",
        user_id="u1",
        vector_store_id="vs1",
        file_urls=[],
    )

    svc.period_dao.add_period.assert_called_once()
    assert "period_id" in result, f"expected period_id in result, got {result!r}"


@pytest.mark.unit
def test_create_period_propagates_canvas_fields():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    svc.create_period(
        course="Canvas Course",
        user_id="u1",
        vector_store_id="vs1",
        file_urls=[],
        canvas_course_id=12345,
        canvas_course_name="Canvas Physics",
    )

    added_period = svc.period_dao.add_period.call_args[0][0]
    assert added_period.canvas_course_id == 12345
    assert added_period.canvas_course_name == "Canvas Physics"


@pytest.mark.unit
def test_get_periods_by_owner():
    svc = _svc()
    svc.period_dao.get_periods_by_owner_id.return_value = [{"period_id": "p1", "status": "pending"}]

    result = svc.get_periods_by_owner("u1")

    svc.period_dao.get_periods_by_owner_id.assert_called_once_with("u1")
    assert result == [{"period_id": "p1", "status": "pending", "has_curriculum": False}]


@pytest.mark.unit
def test_get_period_by_id():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1"}

    result = svc.get_period_by_id("p1")

    svc.period_dao.get_period_by_id.assert_called_once_with("p1")
    assert result == {"period_id": "p1"}


@pytest.mark.unit
def test_update_file_urls():
    svc = _svc()

    svc.update_file_urls("p1", ["url1", "url2"])

    svc.period_dao.update_file_urls.assert_called_once_with("p1", ["url1", "url2"])


@pytest.mark.unit
def test_get_vector_store_id_found():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "vector_store_id": "vs42"}

    result = svc.get_vector_store_id("p1")

    assert result == "vs42", f"expected 'vs42', got {result!r}"


@pytest.mark.unit
def test_get_vector_store_id_not_found():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(ValueError):
        svc.get_vector_store_id("missing")
