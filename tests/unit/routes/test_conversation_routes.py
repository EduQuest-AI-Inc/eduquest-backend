import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from api.deps import get_auth, AuthPayload


def _auth():
    return AuthPayload(sub="user-1", role="student", token="fake-token")


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = lambda: _auth()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestInitiateProfileAssistant:

    @pytest.mark.api
    def test_initiate_profile_assistant_success(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.start_profile_assistant.return_value = {
                "conversation_id": "cid-1", "response": "Hello!"
            }
            resp = client.post("/conversation/initiate-profile-assistant")
        assert resp.status_code == 200
        assert resp.json()["conversation_id"] == "cid-1"
        assert resp.json()["response"] == "Hello!"

    @pytest.mark.api
    def test_initiate_profile_assistant_service_error_returns_500(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.start_profile_assistant.side_effect = RuntimeError("db fail")
            resp = client.post("/conversation/initiate-profile-assistant")
        assert resp.status_code == 500


class TestContinueProfileAssistant:

    @pytest.mark.api
    def test_continue_profile_assistant_success(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_profile_assistant.return_value = {
                "response": "Tell me more", "profile_complete": False
            }
            resp = client.post(
                "/conversation/continue-profile-assistant",
                json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "I like math"},
            )
        assert resp.status_code == 200
        assert "response" in resp.json()
        assert resp.json()["profile_complete"] is False

    @pytest.mark.api
    def test_continue_profile_assistant_missing_required_field_returns_422(self, client):
        resp = client.post(
            "/conversation/continue-profile-assistant",
            json={"conversation_type": "profile", "message": "hi"},
        )
        assert resp.status_code == 422

    @pytest.mark.api
    def test_continue_profile_assistant_value_error_returns_400(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_profile_assistant.side_effect = ValueError("bad input")
            resp = client.post(
                "/conversation/continue-profile-assistant",
                json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 400
        assert "bad input" in resp.json()["detail"]

    @pytest.mark.api
    def test_continue_profile_assistant_lookup_error_returns_404(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_profile_assistant.side_effect = LookupError("not found")
            resp = client.post(
                "/conversation/continue-profile-assistant",
                json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 404

    @pytest.mark.api
    def test_continue_profile_assistant_generic_exception_returns_500(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_profile_assistant.side_effect = RuntimeError("crash")
            resp = client.post(
                "/conversation/continue-profile-assistant",
                json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 500


class TestInitiateUpdateAssistant:

    @pytest.mark.api
    def test_initiate_update_assistant_json_missing_quests_file_returns_400(self, client):
        resp = client.post(
            "/conversation/initiate-update-assistant",
            json={"is_instructor": True},
        )
        assert resp.status_code == 400
        assert "quests_file is required" in resp.json()["detail"]

    @pytest.mark.api
    def test_initiate_update_assistant_student_missing_week_returns_400(self, client):
        resp = client.post(
            "/conversation/initiate-update-assistant",
            json={"quests_file": "[]", "is_instructor": False},
        )
        assert resp.status_code == 400
        assert "week" in resp.json()["detail"]

    @pytest.mark.api
    def test_initiate_update_assistant_student_missing_submission_file_returns_400(self, client):
        resp = client.post(
            "/conversation/initiate-update-assistant",
            json={"quests_file": "[]", "is_instructor": False, "week": 1},
        )
        assert resp.status_code == 400
        assert "submission_file" in resp.json()["detail"]

    @pytest.mark.api
    def test_initiate_update_assistant_instructor_json_success(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.start_update_assistant.return_value = {"conversation_id": "cid-2", "response": "ok"}
            resp = client.post(
                "/conversation/initiate-update-assistant",
                json={"quests_file": "[{}]", "is_instructor": True},
            )
        assert resp.status_code == 200
        assert "conversation_id" in resp.json()

    @pytest.mark.api
    def test_initiate_update_assistant_service_exception_returns_500(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.start_update_assistant.side_effect = RuntimeError("fail")
            resp = client.post(
                "/conversation/initiate-update-assistant",
                json={"quests_file": "[{}]", "is_instructor": True},
            )
        assert resp.status_code == 500


class TestContinueUpdateAssistant:

    @pytest.mark.api
    def test_continue_update_assistant_success(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_update_assistant.return_value = {"response": "Updated plan"}
            resp = client.post(
                "/conversation/continue-update-assistant",
                json={"conversation_id": "cid-1", "message": "adjust week 3"},
            )
        assert resp.status_code == 200
        assert resp.json()["response"] == "Updated plan"

    @pytest.mark.api
    def test_continue_update_assistant_missing_required_field_returns_422(self, client):
        resp = client.post(
            "/conversation/continue-update-assistant",
            json={"message": "hi"},
        )
        assert resp.status_code == 422

    @pytest.mark.api
    def test_continue_update_assistant_value_error_returns_400(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_update_assistant.side_effect = ValueError("bad")
            resp = client.post(
                "/conversation/continue-update-assistant",
                json={"conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 400

    @pytest.mark.api
    def test_continue_update_assistant_lookup_error_returns_404(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_update_assistant.side_effect = LookupError("missing")
            resp = client.post(
                "/conversation/continue-update-assistant",
                json={"conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 404

    @pytest.mark.api
    def test_continue_update_assistant_exception_returns_500(self, client):
        with patch("api.routers.conversation.conversation_service") as mock_svc:
            mock_svc.continue_update_assistant.side_effect = RuntimeError("crash")
            resp = client.post(
                "/conversation/continue-update-assistant",
                json={"conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 500
