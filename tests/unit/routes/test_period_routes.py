import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, require_active_membership, AuthPayload, Role
from services.billing.membership_service import MembershipRequiredError

OWNED_PERIOD = {"period_id": "p1", "owner_id": "user-1", "file_urls": []}
OTHER_PERIOD = {"period_id": "p1", "owner_id": "other-user", "file_urls": []}

VALID_CREATE_PERIOD_PAYLOAD = {
    "name": "Math 101",
    "course_description": "Intro algebra and geometry",
    "grade_level": "9th grade",
    "start_date": "2025-09-01",
    "end_date": "2026-01-15",
}

_TEACHER_AUTH = AuthPayload(sub="user-1", role=Role.TEACHER, token="fake-token")


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: _TEACHER_AUTH
    app.dependency_overrides[require_active_membership] = lambda: _TEACHER_AUTH
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestPeriodListing:

    @pytest.mark.api
    def test_list_periods_success(self, client):
        mock_svc = MagicMock()
        mock_svc.get_periods_by_owner.return_value = [{
            "period_id": "p1", "name": "Math", "status": "approved",
            "processing_status": "ready", "owner_id": "user-1",
            "is_summer_quest": False, "file_urls": [],
        }]
        with patch("routers.period.PeriodManagementService", return_value=mock_svc):
            resp = client.get("/period/periods")
        assert resp.status_code == 200
        assert "periods" in resp.json()

    @pytest.mark.api
    def test_list_periods_exception_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.get_periods_by_owner.side_effect = RuntimeError("db down")
        with patch("routers.period.PeriodManagementService", return_value=mock_svc):
            resp = client.get("/period/periods")
        assert resp.status_code == 500


class TestCreatePeriod:

    @pytest.mark.api
    def test_create_period_success_returns_201(self, client):
        mock_ms = MagicMock()
        mock_ms.check_can_create_class.return_value = None
        mock_pms = MagicMock()
        mock_pms.create_period.return_value = {
            "period_id": "P1-ABCD-1234", "name": "Math 101", "status": "pending",
            "processing_status": "pending", "owner_id": "user-1",
            "is_summer_quest": False, "file_urls": [],
        }
        with patch("routers.period.MembershipService", return_value=mock_ms), \
             patch("routers.period.PeriodManagementService", return_value=mock_pms):
            resp = client.post("/period/create-period", data=VALID_CREATE_PERIOD_PAYLOAD, files=[])
        assert resp.status_code == 201
        assert "message" in resp.json()
        assert "period" in resp.json()

    @pytest.mark.api
    def test_create_period_membership_required_returns_403(self, client):
        mock_access = MagicMock()
        mock_access.status.value = "expired"
        mock_access.trial_ends_at = None
        mock_ms = MagicMock()
        mock_ms.check_can_create_class.side_effect = MembershipRequiredError(mock_access)
        with patch("routers.period.MembershipService", return_value=mock_ms):
            resp = client.post("/period/create-period", data=VALID_CREATE_PERIOD_PAYLOAD, files=[])
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "MEMBERSHIP_REQUIRED"

    @pytest.mark.api
    def test_create_period_missing_name_returns_422(self, client):
        resp = client.post("/period/create-period", data={}, files=[])
        assert resp.status_code == 422

    @pytest.mark.api
    @pytest.mark.parametrize("missing_field", ["course_description", "start_date", "end_date"])
    def test_create_period_missing_required_field_returns_422(self, client, missing_field):
        payload = {k: v for k, v in VALID_CREATE_PERIOD_PAYLOAD.items() if k != missing_field}
        resp = client.post("/period/create-period", data=payload, files=[])
        assert resp.status_code == 422

    @pytest.mark.api
    def test_create_period_summer_quest_skips_membership_gate(self, client):
        mock_ms = MagicMock()
        mock_pms = MagicMock()
        mock_pms.create_period.return_value = {
            "period_id": "SQ-ABCD-1234", "name": "My Quest", "status": "pending",
            "processing_status": "pending", "owner_id": "user-1",
            "is_summer_quest": True, "file_urls": [],
        }
        with patch("routers.period.MembershipService", return_value=mock_ms), \
             patch("routers.period.PeriodManagementService", return_value=mock_pms):
            payload = {k: v for k, v in VALID_CREATE_PERIOD_PAYLOAD.items() if k != "grade_level"}
            payload["is_summer_quest"] = "true"
            resp = client.post("/period/create-period", data=payload, files=[])
        assert resp.status_code == 201
        mock_ms.check_can_create_class.assert_not_called()

    @pytest.mark.api
    def test_create_period_exception_returns_500(self, client):
        mock_ms = MagicMock()
        mock_ms.check_can_create_class.return_value = None
        mock_pms = MagicMock()
        mock_pms.create_period.side_effect = RuntimeError("db error")
        with patch("routers.period.MembershipService", return_value=mock_ms), \
             patch("routers.period.PeriodManagementService", return_value=mock_pms):
            resp = client.post("/period/create-period", data=VALID_CREATE_PERIOD_PAYLOAD, files=[])
        assert resp.status_code == 500


class TestAddFilesToPeriod:

    @pytest.mark.api
    def test_add_files_success(self, client):
        mock_pms = MagicMock()
        mock_pms.get_period_by_id.return_value = OWNED_PERIOD
        with patch("routers.period.PeriodManagementService", return_value=mock_pms):
            resp = client.post(
                "/period/add-files-to-period",
                json={"period_id": "p1", "file_keys": ["s3/key/file.pdf"]},
            )
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_add_files_period_not_found_returns_404(self, client):
        mock_pms = MagicMock()
        mock_pms.get_period_by_id.return_value = None
        with patch("routers.period.PeriodManagementService", return_value=mock_pms):
            resp = client.post(
                "/period/add-files-to-period",
                json={"period_id": "missing", "file_keys": []},
            )
        assert resp.status_code == 404

    @pytest.mark.api
    def test_add_files_not_owner_returns_403(self, client):
        mock_pms = MagicMock()
        mock_pms.get_period_by_id.return_value = OTHER_PERIOD
        with patch("routers.period.PeriodManagementService", return_value=mock_pms):
            resp = client.post(
                "/period/add-files-to-period",
                json={"period_id": "p1", "file_keys": []},
            )
        assert resp.status_code == 403

    @pytest.mark.api
    def test_add_files_service_error_returns_500(self, client):
        mock_pms = MagicMock()
        mock_pms.get_period_by_id.return_value = OWNED_PERIOD
        mock_pms.update_file_urls.side_effect = RuntimeError("upload failed")
        with patch("routers.period.PeriodManagementService", return_value=mock_pms):
            resp = client.post(
                "/period/add-files-to-period",
                json={"period_id": "p1", "file_keys": ["s3/key/file.pdf"]},
            )
        assert resp.status_code == 500


class TestGetFilePresignedUrl:

    @pytest.mark.api
    def test_get_file_presigned_url_success(self, client):
        with patch("routers.period.get_file_presigned_url",
                   return_value="https://s3.amazonaws.com/bucket/file.pdf") as mock_fn:
            resp = client.get("/period/get-file/periods/p1/students/s1/file.pdf")
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://s3.amazonaws.com/bucket/file.pdf"
        mock_fn.assert_called_once_with("periods/p1/students/s1/file.pdf")

    @pytest.mark.api
    def test_get_file_presigned_url_exception_returns_500(self, client):
        with patch("routers.period.get_file_presigned_url") as mock_fn:
            mock_fn.side_effect = RuntimeError("S3 error")
            resp = client.get("/period/get-file/periods/p1/file.pdf")
        assert resp.status_code == 500
