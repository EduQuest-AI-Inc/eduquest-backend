import pytest
from unittest.mock import MagicMock

from services.period.period_management_service import PeriodManagementService
from exceptions.not_found_error import NotFoundError


def _svc():
    svc = PeriodManagementService.__new__(PeriodManagementService)
    svc.period_dao = MagicMock()
    svc.enrollment_dao = MagicMock()
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
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "status": "draft"}

    result = svc.get_period_by_id("p1")

    svc.period_dao.get_period_by_id.assert_called_once_with("p1")
    assert result == {"period_id": "p1", "status": "draft", "has_curriculum": True}


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

    with pytest.raises(NotFoundError):
        svc.get_vector_store_id("missing")


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_status_delegates_to_dao():
    svc = _svc()

    svc.update_status("p1", "active")

    svc.period_dao.update_status.assert_called_once_with("p1", "active")


# ---------------------------------------------------------------------------
# update_setup
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_setup_updates_and_returns_period():
    svc = _svc()
    updated_period = {"period_id": "p1", "name": "New Name"}
    svc.period_dao.get_period_by_id.return_value = updated_period

    result = svc.update_setup("p1", {"name": "New Name"})

    svc.period_dao.update_period.assert_called_once_with("p1", {"name": "New Name"})
    svc.period_dao.get_period_by_id.assert_called_once_with("p1")
    assert result == updated_period


@pytest.mark.unit
def test_update_setup_returns_none_when_period_not_found():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.update_setup("missing", {"name": "Ghost"})

    assert result is None


# ---------------------------------------------------------------------------
# update_processing_status
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_processing_status_delegates_to_dao():
    svc = _svc()

    svc.update_processing_status("p1", "processing")

    svc.period_dao.update_period.assert_called_once_with("p1", {"processing_status": "processing"})


# ---------------------------------------------------------------------------
# update_vector_store_id
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_vector_store_id_delegates_to_dao():
    svc = _svc()

    svc.update_vector_store_id("p1", "vs99")

    svc.period_dao.update_period.assert_called_once_with("p1", {"vector_store_id": "vs99"})


# ---------------------------------------------------------------------------
# update_file_vector_store_ids
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_file_vector_store_ids_delegates_to_dao():
    svc = _svc()
    ids = ["fvs1", "fvs2"]

    svc.update_file_vector_store_ids("p1", ids)

    svc.period_dao.update_period.assert_called_once_with("p1", {"file_vector_store_ids": ids})


# ---------------------------------------------------------------------------
# delete_period
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_delete_period_raises_not_found_when_missing():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.delete_period("missing", "u1")


@pytest.mark.unit
def test_delete_period_raises_permission_error_when_not_owner():
    from exceptions.permission_error import PermissionError

    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "other_user"}

    with pytest.raises(PermissionError):
        svc.delete_period("p1", "u1")


@pytest.mark.unit
def test_delete_period_deletes_vector_store_and_s3_files(monkeypatch):
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {
        "period_id": "p1",
        "owner_id": "u1",
        "vector_store_id": "vs42",
        "file_urls": ["s3/key1", "s3/key2"],
    }
    svc.period_dao.get_forks_by_period.return_value = []

    mock_delete_store = MagicMock()
    mock_delete_s3 = MagicMock()
    import services.period.period_management_service as svc_module
    monkeypatch.setattr(svc_module.openai_vector_store, "delete_store", mock_delete_store)
    monkeypatch.setattr(svc_module, "delete_files_from_s3", mock_delete_s3)

    svc.delete_period("p1", "u1")

    mock_delete_store.assert_called_once_with("vs42")
    mock_delete_s3.assert_called_once_with(["s3/key1", "s3/key2"])
    svc.period_dao.delete_period.assert_called_once_with("p1")


@pytest.mark.unit
def test_delete_period_skips_vector_store_when_none(monkeypatch):
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {
        "period_id": "p1",
        "owner_id": "u1",
        "vector_store_id": None,
        "file_urls": [],
    }
    svc.period_dao.get_forks_by_period.return_value = []

    mock_delete_store = MagicMock()
    mock_delete_s3 = MagicMock()
    import services.period.period_management_service as svc_module
    monkeypatch.setattr(svc_module.openai_vector_store, "delete_store", mock_delete_store)
    monkeypatch.setattr(svc_module, "delete_files_from_s3", mock_delete_s3)

    svc.delete_period("p1", "u1")

    mock_delete_store.assert_not_called()
    mock_delete_s3.assert_not_called()
    svc.period_dao.delete_period.assert_called_once_with("p1")


@pytest.mark.unit
def test_delete_period_skips_local_file_urls(monkeypatch):
    """File URLs prefixed with 'local/' are not passed to S3 delete."""
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {
        "period_id": "p1",
        "owner_id": "u1",
        "vector_store_id": None,
        "file_urls": ["local/file.pdf", "s3/remote.pdf"],
    }
    svc.period_dao.get_forks_by_period.return_value = []

    mock_delete_store = MagicMock()
    mock_delete_s3 = MagicMock()
    import services.period.period_management_service as svc_module
    monkeypatch.setattr(svc_module.openai_vector_store, "delete_store", mock_delete_store)
    monkeypatch.setattr(svc_module, "delete_files_from_s3", mock_delete_s3)

    svc.delete_period("p1", "u1")

    mock_delete_s3.assert_called_once_with(["s3/remote.pdf"])


# ---------------------------------------------------------------------------
# is_summer_quest
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_create_period_summer_quest_flag_stored():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.create_period(
        course="My Quest",
        user_id="u1",
        vector_store_id="vs1",
        file_urls=[],
        is_summer_quest=True,
    )

    assert result["is_summer_quest"] is True
    added_period = svc.period_dao.add_period.call_args[0][0]
    assert added_period.is_summer_quest is True


@pytest.mark.unit
def test_create_period_summer_quest_auto_enrolls_creator():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    result = svc.create_period(
        course="My Quest",
        user_id="u1",
        vector_store_id="vs1",
        file_urls=[],
        is_summer_quest=True,
    )

    svc.enrollment_dao.add_enrollment.assert_called_once()
    enrollment_arg = svc.enrollment_dao.add_enrollment.call_args[0][0]
    assert enrollment_arg.user_id == "u1"
    assert enrollment_arg.period_id == result["period_id"]
    assert enrollment_arg.semester == "Summer"


@pytest.mark.unit
def test_create_period_non_summer_quest_does_not_enroll():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    svc.create_period(
        course="Normal Class",
        user_id="u1",
        vector_store_id="vs1",
        file_urls=[],
        is_summer_quest=False,
    )

    svc.enrollment_dao.add_enrollment.assert_not_called()


# ---------------------------------------------------------------------------
# archive_period
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_archive_period_raises_not_found_when_missing():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.archive_period("missing", "u1")


@pytest.mark.unit
def test_archive_period_raises_permission_error_when_not_owner():
    from exceptions.permission_error import PermissionError

    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {"period_id": "p1", "owner_id": "other_user"}

    with pytest.raises(PermissionError):
        svc.archive_period("p1", "u1")


@pytest.mark.unit
def test_archive_period_delegates_to_dao_and_returns_enriched():
    svc = _svc()
    base_period = {"period_id": "p1", "owner_id": "u1", "status": "approved"}
    archived_period = {**base_period, "archived_at": "2025-01-01T00:00:00+00:00"}
    # First call is the pre-fetch passed via period=, second is the re-fetch after archive
    svc.period_dao.get_period_by_id.return_value = archived_period

    result = svc.archive_period("p1", "u1", period=base_period)

    svc.period_dao.archive_period.assert_called_once_with("p1")
    assert result.get("has_curriculum") is True  # enriched
    assert result.get("period_id") == "p1"


# ---------------------------------------------------------------------------
# unarchive_period
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_unarchive_period_raises_not_found_when_missing():
    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = None

    with pytest.raises(NotFoundError):
        svc.unarchive_period("missing", "u1")


@pytest.mark.unit
def test_unarchive_period_raises_permission_error_when_not_owner():
    from exceptions.permission_error import PermissionError

    svc = _svc()
    svc.period_dao.get_period_by_id.return_value = {
        "period_id": "p1",
        "owner_id": "other_user",
        "archived_at": "2025-01-01T00:00:00+00:00",
    }

    with pytest.raises(PermissionError):
        svc.unarchive_period("p1", "u1")


@pytest.mark.unit
def test_unarchive_period_delegates_to_dao_and_returns_enriched():
    svc = _svc()
    archived_period = {
        "period_id": "p1",
        "owner_id": "u1",
        "status": "approved",
        "archived_at": "2025-01-01T00:00:00+00:00",
    }
    unarchived_period = {**archived_period, "archived_at": None}
    # Re-fetch after unarchive returns the unarchived state
    svc.period_dao.get_period_by_id.return_value = unarchived_period

    result = svc.unarchive_period("p1", "u1", period=archived_period)

    svc.period_dao.unarchive_period.assert_called_once_with("p1")
    assert result.get("has_curriculum") is True  # enriched
    assert result.get("archived_at") is None
