import pytest
from data_access.period_dao import PeriodDAO
from models.period import Period

_ID = "test-integration-period-dao"
_OWNER = "test-integration-period-owner"


def _period():
    return Period(period_id=_ID, owner_id=_OWNER, name="Integration Period", vector_store_id="vs-test")


@pytest.mark.integration
def test_add_and_get_period(supabase_required):
    dao = PeriodDAO()
    try:
        dao.add_period(_period())
        result = dao.get_period_by_id(_ID)
        assert result is not None
        assert result["period_id"] == _ID
        assert result["name"] == "Integration Period"
    finally:
        dao.delete_period(_ID)


@pytest.mark.integration
def test_update_period(supabase_required):
    dao = PeriodDAO()
    try:
        dao.add_period(_period())
        dao.update_period(_ID, {"name": "Renamed Period"})
        result = dao.get_period_by_id(_ID)
        assert result["name"] == "Renamed Period"
    finally:
        dao.delete_period(_ID)


@pytest.mark.integration
def test_get_periods_by_owner_id(supabase_required):
    dao = PeriodDAO()
    try:
        dao.add_period(_period())
        results = dao.get_periods_by_owner_id(_OWNER)
        assert any(r["period_id"] == _ID for r in results)
    finally:
        dao.delete_period(_ID)


@pytest.mark.integration
def test_update_file_urls(supabase_required):
    dao = PeriodDAO()
    try:
        dao.add_period(_period())
        dao.update_file_urls(_ID, ["https://s3.example.com/file1.pdf"])
        result = dao.get_period_by_id(_ID)
        assert "https://s3.example.com/file1.pdf" in result["file_urls"]
    finally:
        dao.delete_period(_ID)


@pytest.mark.integration
def test_delete_period(supabase_required):
    dao = PeriodDAO()
    dao.add_period(_period())
    dao.delete_period(_ID)
    assert dao.get_period_by_id(_ID) is None
