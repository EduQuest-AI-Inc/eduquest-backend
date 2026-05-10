import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload, Role


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="user-1", role=Role.STUDENT, token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestInitiateLTGConversation:

    @pytest.mark.api
    def test_initiate_ltg_success(self, client):
        with patch("routers.ltg.EnrollmentService") as mock_es, \
             patch("routers.ltg.period_service") as mock_ps:
            mock_es.return_value.check_enrolled.return_value = None
            mock_ps.initiate_ltg_conversation.return_value = {
                "response": "What are your goals?", "conversation_id": "cid-1"
            }
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        assert resp.status_code == 200
        mock_ps.initiate_ltg_conversation.assert_called_once_with("user-1", "p1")

    @pytest.mark.api
    def test_initiate_ltg_missing_period_id_returns_422(self, client):
        resp = client.post("/period/initiate-ltg-conversation", json={})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_initiate_ltg_value_error_returns_400(self, client):
        with patch("routers.ltg.EnrollmentService") as mock_es, \
             patch("routers.ltg.period_service") as mock_ps:
            mock_es.return_value.check_enrolled.return_value = None
            mock_ps.initiate_ltg_conversation.side_effect = ValueError("invalid period")
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "bad"})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_initiate_ltg_lookup_error_returns_404(self, client):
        with patch("routers.ltg.EnrollmentService") as mock_es, \
             patch("routers.ltg.period_service") as mock_ps:
            mock_es.return_value.check_enrolled.return_value = None
            mock_ps.initiate_ltg_conversation.side_effect = LookupError("not found")
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_initiate_ltg_exception_returns_500(self, client):
        with patch("routers.ltg.EnrollmentService") as mock_es, \
             patch("routers.ltg.period_service") as mock_ps:
            mock_es.return_value.check_enrolled.return_value = None
            mock_ps.initiate_ltg_conversation.side_effect = RuntimeError("crash")
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        assert resp.status_code == 500


class TestContinueLTGConversation:

    @pytest.mark.api
    def test_continue_ltg_success(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.continue_ltg_conversation.return_value = {
                "response": "Great goal!", "conversation_id": "cid-1"
            }
            resp = client.post(
                "/period/continue-ltg-conversation",
                json={
                    "conversation_type": "ltg", "conversation_id": "cid-1",
                    "message": "I want to improve algebra", "period_id": "p1",
                },
            )
        assert resp.status_code == 200

    @pytest.mark.api
    def test_continue_ltg_missing_required_fields_returns_422(self, client):
        resp = client.post("/period/continue-ltg-conversation", json={"message": "hi"})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_continue_ltg_optional_period_id_omitted(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.continue_ltg_conversation.return_value = {"response": "ok"}
            resp = client.post(
                "/period/continue-ltg-conversation",
                json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 200

    @pytest.mark.api
    def test_continue_ltg_value_error_returns_400(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.continue_ltg_conversation.side_effect = ValueError("bad")
            resp = client.post(
                "/period/continue-ltg-conversation",
                json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 400

    @pytest.mark.api
    def test_continue_ltg_exception_returns_500(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.continue_ltg_conversation.side_effect = RuntimeError("crash")
            resp = client.post(
                "/period/continue-ltg-conversation",
                json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 500


class TestInitiateHomeworkAgent:

    @pytest.mark.api
    def test_initiate_homework_agent_with_explicit_user_id(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.start_homework_agent.return_value = {"quests": []}
            resp = client.post(
                "/period/initiate-homework-agent",
                json={"period_id": "p1", "user_id": "student-99"},
            )
        assert resp.status_code == 200
        mock_ps.start_homework_agent.assert_called_once_with("student-99", "p1")

    @pytest.mark.api
    def test_initiate_homework_agent_defaults_to_auth_sub(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.start_homework_agent.return_value = {"quests": []}
            resp = client.post(
                "/period/initiate-homework-agent",
                json={"period_id": "p1"},
            )
        assert resp.status_code == 200
        mock_ps.start_homework_agent.assert_called_once_with("user-1", "p1")

    @pytest.mark.api
    def test_initiate_homework_agent_value_error_returns_400(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.start_homework_agent.side_effect = ValueError("bad period")
            resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_initiate_homework_agent_lookup_error_returns_404(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.start_homework_agent.side_effect = LookupError("missing")
            resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_initiate_homework_agent_exception_returns_500(self, client):
        with patch("routers.ltg.period_service") as mock_ps:
            mock_ps.start_homework_agent.side_effect = RuntimeError("crash")
            resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        assert resp.status_code == 500
