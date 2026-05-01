"""Integration tests for SupabaseBaseDAO helpers using PeriodDAO as the vehicle."""
import pytest
from data_access.period_dao import PeriodDAO
from models.period import Period

_ID = "test-integration-base-dao"


@pytest.mark.integration
def test_insert_and_select_by_id(supabase_required):
    dao = PeriodDAO()
    period = Period(period_id=_ID, owner_id="test-owner", name="Base DAO Test", vector_store_id="vs-test")
    try:
        dao.add_period(period)
        result = dao.get_period_by_id(_ID)
        assert result is not None
        assert result["period_id"] == _ID
    finally:
        dao.delete_period(_ID)


@pytest.mark.integration
def test_select_eq(supabase_required):
    dao = PeriodDAO()
    period = Period(period_id=_ID, owner_id="test-eq-owner", name="Select EQ Test", vector_store_id="vs-test")
    try:
        dao.add_period(period)
        results = dao.get_periods_by_owner_id("test-eq-owner")
        assert any(r["period_id"] == _ID for r in results)
    finally:
        dao.delete_period(_ID)


@pytest.mark.integration
def test_update(supabase_required):
    dao = PeriodDAO()
    period = Period(period_id=_ID, owner_id="test-owner", name="Original Name", vector_store_id="vs-test")
    try:
        dao.add_period(period)
        dao.update_period(_ID, {"name": "Updated Name"})
        result = dao.get_period_by_id(_ID)
        assert result["name"] == "Updated Name", f"expected 'Updated Name', got {result['name']!r}"
    finally:
        dao.delete_period(_ID)


@pytest.mark.integration
def test_delete(supabase_required):
    dao = PeriodDAO()
    period = Period(period_id=_ID, owner_id="test-owner", name="Delete Test", vector_store_id="vs-test")
    dao.add_period(period)
    dao.delete_period(_ID)
    assert dao.get_period_by_id(_ID) is None
