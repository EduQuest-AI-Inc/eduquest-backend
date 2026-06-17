import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload
from routers.conversation import _get_conversation_service


def _auth():
    return AuthPayload(sub="user-1", role="student", token="fake-token")


def _mock_svc():
    svc = MagicMock()
    # These router methods use `await svc.<method>(...)`, so they must be AsyncMock.
    svc.start_profile_assistant = AsyncMock()
    svc.continue_profile_assistant = AsyncMock()
    return svc


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_auth] = lambda: _auth()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestInitiateProfileAssistant:

    @pytest.mark.api
    def test_initiate_profile_assistant_success(self, client):
        mock_svc = _mock_svc()
        mock_svc.start_profile_assistant.return_value = {
            "conversation_id": "cid-1", "response": "Hello!"
        }
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post("/conversation/initiate-profile-assistant")
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 200
        assert resp.json()["conversation_id"] == "cid-1"
        assert resp.json()["response"] == "Hello!"

    @pytest.mark.api
    def test_initiate_profile_assistant_service_error_returns_500(self, client):
        mock_svc = _mock_svc()
        mock_svc.start_profile_assistant.side_effect = RuntimeError("db fail")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post("/conversation/initiate-profile-assistant")
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 500


class TestContinueProfileAssistant:

    @pytest.mark.api
    def test_continue_profile_assistant_success(self, client):
        mock_svc = _mock_svc()
        mock_svc.continue_profile_assistant.return_value = {
            "response": "Tell me more", "profile_complete": False
        }
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-profile-assistant",
            json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "I like math"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
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
        mock_svc = _mock_svc()
        mock_svc.continue_profile_assistant.side_effect = ValueError("bad input")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-profile-assistant",
            json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 400
        assert "bad input" in resp.json()["detail"]

    @pytest.mark.api
    def test_continue_profile_assistant_lookup_error_returns_404(self, client):
        mock_svc = _mock_svc()
        mock_svc.continue_profile_assistant.side_effect = LookupError("not found")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-profile-assistant",
            json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 404

    @pytest.mark.api
    def test_continue_profile_assistant_generic_exception_returns_500(self, client):
        mock_svc = _mock_svc()
        mock_svc.continue_profile_assistant.side_effect = RuntimeError("crash")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-profile-assistant",
            json={"conversation_type": "profile", "conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
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
        mock_svc = _mock_svc()
        mock_svc.start_update_assistant.return_value = {"conversation_id": "cid-2", "response": "ok"}
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/initiate-update-assistant",
            json={"quests_file": "[{}]", "is_instructor": True},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 200
        assert "conversation_id" in resp.json()

    @pytest.mark.api
    def test_initiate_update_assistant_service_exception_returns_500(self, client):
        mock_svc = _mock_svc()
        mock_svc.start_update_assistant.side_effect = RuntimeError("fail")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/initiate-update-assistant",
            json={"quests_file": "[{}]", "is_instructor": True},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 500


class TestContinueUpdateAssistant:

    @pytest.mark.api
    def test_continue_update_assistant_success(self, client):
        mock_svc = _mock_svc()
        mock_svc.continue_update_assistant.return_value = {"response": "Updated plan"}
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-update-assistant",
            json={"conversation_id": "cid-1", "message": "adjust week 3"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
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
        mock_svc = _mock_svc()
        mock_svc.continue_update_assistant.side_effect = ValueError("bad")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-update-assistant",
            json={"conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 400

    @pytest.mark.api
    def test_continue_update_assistant_lookup_error_returns_404(self, client):
        mock_svc = _mock_svc()
        mock_svc.continue_update_assistant.side_effect = LookupError("missing")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-update-assistant",
            json={"conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 404

    @pytest.mark.api
    def test_continue_update_assistant_exception_returns_500(self, client):
        mock_svc = _mock_svc()
        mock_svc.continue_update_assistant.side_effect = RuntimeError("crash")
        app.dependency_overrides[_get_conversation_service] = lambda: mock_svc
        resp = client.post(
            "/conversation/continue-update-assistant",
            json={"conversation_id": "cid-1", "message": "hi"},
        )
        app.dependency_overrides.pop(_get_conversation_service, None)
        assert resp.status_code == 500
