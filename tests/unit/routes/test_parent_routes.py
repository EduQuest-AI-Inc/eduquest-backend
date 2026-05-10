import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, require_active_membership, AuthPayload, Role

_PARENT_AUTH = AuthPayload(sub="parent-1", role=Role.PARENT, token="fake-token")


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = lambda: _PARENT_AUTH
    app.dependency_overrides[require_active_membership] = lambda: _PARENT_AUTH
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestMyPeriods:

    @pytest.mark.api
    def test_my_periods_returns_list(self, client):
        with patch("routers.parent.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.return_value = [{"period_id": "p1", "name": "Math"}]
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 200
        assert resp.json()["periods"] == [{"period_id": "p1", "name": "Math"}]
        mock_pms.get_periods_by_owner.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_my_periods_empty_returns_empty_list(self, client):
        with patch("routers.parent.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.return_value = []
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 200
        assert resp.json()["periods"] == []

    @pytest.mark.api
    def test_my_periods_service_error_returns_500(self, client):
        with patch("routers.parent.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.side_effect = RuntimeError("db down")
            resp = client.get("/parent/my-periods")
        assert resp.status_code == 500


class TestGenerateInvite:

    @pytest.mark.api
    def test_generate_invite_returns_201(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.generate_invite.return_value = {
                "code": "ABCD1234", "expires_at": "2026-05-01T00:00:00+00:00"
            }
            resp = client.post("/parent/generate-invite")
        assert resp.status_code == 201
        assert resp.json()["code"] == "ABCD1234"
        assert "expires_at" in resp.json()
        mock_ps.generate_invite.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_generate_invite_service_error_returns_500(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.generate_invite.side_effect = RuntimeError("fail")
            resp = client.post("/parent/generate-invite")
        assert resp.status_code == 500


class TestGetStudents:

    @pytest.mark.api
    def test_get_students_returns_list(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.get_linked_students.return_value = [
                {"user_id": "s1", "first_name": "Alice", "last_name": "Smith",
                 "grade": "10", "email": "alice@eduquestai.org"}
            ]
            resp = client.get("/parent/students")
        assert resp.status_code == 200
        assert len(resp.json()["students"]) == 1
        mock_ps.get_linked_students.assert_called_once_with("parent-1")

    @pytest.mark.api
    def test_get_students_empty_returns_empty_list(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.get_linked_students.return_value = []
            resp = client.get("/parent/students")
        assert resp.status_code == 200
        assert resp.json()["students"] == []

    @pytest.mark.api
    def test_get_students_service_error_returns_500(self, client):
        with patch("routers.parent.parent_service") as mock_ps:
            mock_ps.get_linked_students.side_effect = RuntimeError("fail")
            resp = client.get("/parent/students")
        assert resp.status_code == 500
