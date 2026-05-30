import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, get_period, AuthPayload, Role
from routers.slides import _get_slides_service

_PERIOD_ID = "period-1"
_OWNER_ID = "teacher-1"
_OWNED_PERIOD = {"period_id": _PERIOD_ID, "owner_id": _OWNER_ID}

_TEACHER_AUTH = AuthPayload(sub=_OWNER_ID, role=Role.TEACHER, token="fake-token")


@pytest.fixture
def teacher_client():
    app.dependency_overrides[get_auth] = lambda: _TEACHER_AUTH
    app.dependency_overrides[get_period] = lambda: _OWNED_PERIOD
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestRestartPptxGeneration:

    @pytest.mark.api
    def test_restart_returns_503_when_pptx_disabled(self, teacher_client, monkeypatch):
        monkeypatch.setenv("PPTX_GENERATION_ENABLED", "false")
        mock_ss = MagicMock()
        app.dependency_overrides[_get_slides_service] = lambda: mock_ss
        resp = teacher_client.post(f"/slides/{_PERIOD_ID}/pptx/restart")
        app.dependency_overrides.pop(_get_slides_service, None)
        assert resp.status_code == 503
        assert "disabled" in resp.json()["detail"].lower()
        mock_ss.restart_batch.assert_not_called()

    @pytest.mark.api
    def test_restart_returns_202_when_pptx_enabled(self, teacher_client, monkeypatch):
        monkeypatch.setenv("PPTX_GENERATION_ENABLED", "true")
        mock_ss = MagicMock()
        mock_ss.restart_batch.return_value = 2
        app.dependency_overrides[_get_slides_service] = lambda: mock_ss
        resp = teacher_client.post(f"/slides/{_PERIOD_ID}/pptx/restart")
        app.dependency_overrides.pop(_get_slides_service, None)
        assert resp.status_code == 202
        assert resp.json()["queued"] == 2
