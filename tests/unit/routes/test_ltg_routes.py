import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload, Role
from routers.ltg import _get_period_service


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="user-1", role=Role.STUDENT, token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestInitiateLTGConversation:

    @pytest.fixture(autouse=True)
    def mock_enrollment(self):
        with patch("routers.ltg.EnrollmentService") as m:
            m.return_value.check_enrolled.return_value = None
            yield m

    @pytest.mark.api
    def test_initiate_ltg_success(self, client, mock_enrollment):
        mock_ps = MagicMock()
        mock_ps.initiate_ltg_conversation = AsyncMock(return_value={
            "response": "What are your goals?", "conversation_id": "cid-1"
        })
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 200
        mock_ps.initiate_ltg_conversation.assert_called_once_with("user-1", "p1")
        mock_enrollment.return_value.check_enrolled.assert_called_once_with("user-1", "p1")

    @pytest.mark.api
    def test_initiate_ltg_missing_period_id_returns_422(self, client):
        resp = client.post("/period/initiate-ltg-conversation", json={})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_initiate_ltg_value_error_returns_400(self, client):
        mock_ps = MagicMock()
        mock_ps.initiate_ltg_conversation = AsyncMock(side_effect=ValueError("invalid period"))
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "bad"})
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 400

    @pytest.mark.api
    def test_initiate_ltg_lookup_error_returns_404(self, client):
        mock_ps = MagicMock()
        mock_ps.initiate_ltg_conversation = AsyncMock(side_effect=LookupError("not found"))
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 404

    @pytest.mark.api
    def test_initiate_ltg_exception_returns_500(self, client):
        mock_ps = MagicMock()
        mock_ps.initiate_ltg_conversation = AsyncMock(side_effect=RuntimeError("crash"))
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 500


class TestContinueLTGConversation:

    @pytest.mark.api
    def test_continue_ltg_success(self, client):
        mock_ps = MagicMock()
        mock_ps.continue_ltg_conversation = AsyncMock(return_value={
            "response": "Great goal!", "conversation_id": "cid-1"
        })
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post(
            "/period/continue-ltg-conversation",
            json={
                "conversation_type": "ltg", "conversation_id": "cid-1",
                "message": "I want to improve algebra", "period_id": "p1",
            },
        )
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 200

    @pytest.mark.api
    def test_continue_ltg_missing_required_fields_returns_422(self, client):
        resp = client.post("/period/continue-ltg-conversation", json={"message": "hi"})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_continue_ltg_optional_period_id_omitted(self, client):
        mock_ps = MagicMock()
        mock_ps.continue_ltg_conversation = AsyncMock(return_value={"response": "ok"})
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post(
            "/period/continue-ltg-conversation",
            json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 200

    @pytest.mark.api
    def test_continue_ltg_value_error_returns_400(self, client):
        mock_ps = MagicMock()
        mock_ps.continue_ltg_conversation = AsyncMock(side_effect=ValueError("bad"))
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post(
            "/period/continue-ltg-conversation",
            json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 400

    @pytest.mark.api
    def test_continue_ltg_exception_returns_500(self, client):
        mock_ps = MagicMock()
        mock_ps.continue_ltg_conversation = AsyncMock(side_effect=RuntimeError("crash"))
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post(
            "/period/continue-ltg-conversation",
            json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 500


class TestInitiateHomeworkAgent:

    @pytest.fixture(autouse=True)
    def mock_enrollment(self):
        with patch("routers.ltg.EnrollmentService") as m:
            m.return_value.check_enrolled.return_value = None
            yield m

    @pytest.mark.api
    def test_initiate_homework_agent_with_explicit_user_id(self, client):
        mock_ps = MagicMock()
        mock_ps.start_homework_agent.return_value = {"quests": []}
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        mock_period_mgmt = MagicMock()
        mock_period_mgmt.get_period_by_id.return_value = {"owner_id": "user-1"}
        with patch("routers.ltg.PeriodManagementService", return_value=mock_period_mgmt):
            resp = client.post(
                "/period/initiate-homework-agent",
                json={"period_id": "p1", "user_id": "student-99"},
            )
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 200
        mock_ps.start_homework_agent.assert_called_once_with("student-99", "p1")

    @pytest.mark.api
    def test_initiate_homework_agent_defaults_to_auth_sub(self, client):
        mock_ps = MagicMock()
        mock_ps.start_homework_agent.return_value = {"quests": []}
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post(
            "/period/initiate-homework-agent",
            json={"period_id": "p1"},
        )
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 200
        mock_ps.start_homework_agent.assert_called_once_with("user-1", "p1")

    @pytest.mark.api
    def test_initiate_homework_agent_value_error_returns_400(self, client):
        mock_ps = MagicMock()
        mock_ps.start_homework_agent.side_effect = ValueError("bad period")
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 400

    @pytest.mark.api
    def test_initiate_homework_agent_lookup_error_returns_404(self, client):
        mock_ps = MagicMock()
        mock_ps.start_homework_agent.side_effect = LookupError("missing")
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 404

    @pytest.mark.api
    def test_initiate_homework_agent_exception_returns_500(self, client):
        mock_ps = MagicMock()
        mock_ps.start_homework_agent.side_effect = RuntimeError("crash")
        app.dependency_overrides[_get_period_service] = lambda: mock_ps
        resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        app.dependency_overrides.pop(_get_period_service, None)
        assert resp.status_code == 500
