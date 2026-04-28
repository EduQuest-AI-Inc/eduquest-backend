import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from api.deps import get_auth, AuthPayload

OWNED_PERIOD = {"period_id": "p1", "owner_id": "user-1", "file_urls": []}
OTHER_PERIOD = {"period_id": "p1", "owner_id": "other-user", "file_urls": []}
APPROVED_TEACHER = {"user_id": "user-1", "pilot_approved": True}
UNAPPROVED_TEACHER = {"user_id": "user-1", "pilot_approved": False}


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="user-1", role="teacher", token="fake-token"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestInitiateLTGConversation:

    @pytest.mark.api
    def test_initiate_ltg_success(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.initiate_ltg_conversation.return_value = {
                "response": "What are your goals?", "conversation_id": "cid-1"
            }
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        assert resp.status_code == 200
        mock_ps.initiate_ltg_conversation.assert_called_once_with("fake-token", "p1")

    @pytest.mark.api
    def test_initiate_ltg_missing_period_id_returns_422(self, client):
        resp = client.post("/period/initiate-ltg-conversation", json={})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_initiate_ltg_value_error_returns_400(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.initiate_ltg_conversation.side_effect = ValueError("invalid period")
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "bad"})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_initiate_ltg_lookup_error_returns_404(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.initiate_ltg_conversation.side_effect = LookupError("not found")
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_initiate_ltg_exception_returns_500(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.initiate_ltg_conversation.side_effect = RuntimeError("crash")
            resp = client.post("/period/initiate-ltg-conversation", json={"period_id": "p1"})
        assert resp.status_code == 500


class TestContinueLTGConversation:

    @pytest.mark.api
    def test_continue_ltg_success(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
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
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.continue_ltg_conversation.return_value = {"response": "ok"}
            resp = client.post(
                "/period/continue-ltg-conversation",
                json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 200

    @pytest.mark.api
    def test_continue_ltg_value_error_returns_400(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.continue_ltg_conversation.side_effect = ValueError("bad")
            resp = client.post(
                "/period/continue-ltg-conversation",
                json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 400

    @pytest.mark.api
    def test_continue_ltg_exception_returns_500(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.continue_ltg_conversation.side_effect = RuntimeError("crash")
            resp = client.post(
                "/period/continue-ltg-conversation",
                json={"conversation_type": "ltg", "conversation_id": "cid-1", "message": "hi"},
            )
        assert resp.status_code == 500


class TestInitiateHomeworkAgent:

    @pytest.mark.api
    def test_initiate_homework_agent_with_explicit_user_id(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.start_homework_agent.return_value = {"quests": []}
            resp = client.post(
                "/period/initiate-homework-agent",
                json={"period_id": "p1", "user_id": "student-99"},
            )
        assert resp.status_code == 200
        mock_ps.start_homework_agent.assert_called_once_with("fake-token", "student-99", "p1")

    @pytest.mark.api
    def test_initiate_homework_agent_defaults_to_auth_sub(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.start_homework_agent.return_value = {"quests": []}
            resp = client.post(
                "/period/initiate-homework-agent",
                json={"period_id": "p1"},
            )
        assert resp.status_code == 200
        mock_ps.start_homework_agent.assert_called_once_with("fake-token", "user-1", "p1")

    @pytest.mark.api
    def test_initiate_homework_agent_value_error_returns_400(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.start_homework_agent.side_effect = ValueError("bad period")
            resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_initiate_homework_agent_lookup_error_returns_404(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.start_homework_agent.side_effect = LookupError("missing")
            resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_initiate_homework_agent_exception_returns_500(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.start_homework_agent.side_effect = RuntimeError("crash")
            resp = client.post("/period/initiate-homework-agent", json={"period_id": "p1"})
        assert resp.status_code == 500


class TestPeriodListing:

    @pytest.mark.api
    def test_list_periods_success(self, client):
        with patch("api.routers.period.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.return_value = [{"period_id": "p1"}]
            resp = client.get("/period/periods")
        assert resp.status_code == 200
        assert "periods" in resp.json()

    @pytest.mark.api
    def test_list_periods_exception_returns_500(self, client):
        with patch("api.routers.period.period_management_service") as mock_pms:
            mock_pms.get_periods_by_owner.side_effect = RuntimeError("db down")
            resp = client.get("/period/periods")
        assert resp.status_code == 500

    @pytest.mark.api
    def test_my_periods_success(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.get_my_periods.return_value = [{"period_id": "p2"}]
            resp = client.get("/period/my-periods")
        assert resp.status_code == 200
        assert resp.json() == [{"period_id": "p2"}]
        mock_ps.get_my_periods.assert_called_once_with("user-1")


class TestVerifyAndUnenroll:

    @pytest.mark.api
    def test_verify_period_success(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.verify_period_id.return_value = {"period_id": "p1", "name": "Math"}
            resp = client.post("/period/verify-period", json={"period_id": "p1"})
        assert resp.status_code == 200
        assert "message" in resp.json()
        assert resp.json()["period"]["period_id"] == "p1"

    @pytest.mark.api
    def test_unenroll_success(self, client):
        with patch("api.routers.period.period_service") as mock_ps:
            mock_ps.unenroll_from_period.return_value = {"message": "Unenrolled"}
            resp = client.post("/period/unenroll", json={"period_id": "p1"})
        assert resp.status_code == 200


class TestAcceptParentInvite:

    @pytest.mark.api
    def test_accept_invite_success(self, client):
        with patch("api.routers.period.parent_service_p") as mock_parent:
            mock_parent.accept_invite.return_value = {
                "message": "Successfully linked", "student_id": "user-1", "parent_id": "parent-1"
            }
            resp = client.post("/period/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 200
        mock_parent.accept_invite.assert_called_once_with("user-1", "ABCD1234")

    @pytest.mark.api
    def test_accept_invite_empty_code_returns_400(self, client):
        resp = client.post("/period/accept-parent-invite", json={"code": "   "})
        assert resp.status_code == 400
        assert "detail" in resp.json()

    @pytest.mark.api
    def test_accept_invite_expired_returns_410(self, client):
        with patch("api.routers.period.parent_service_p") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Invite code has expired")
            resp = client.post("/period/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 410

    @pytest.mark.api
    def test_accept_invite_already_used_returns_410(self, client):
        with patch("api.routers.period.parent_service_p") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Invite code has already been used")
            resp = client.post("/period/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 410

    @pytest.mark.api
    def test_accept_invite_invalid_code_returns_404(self, client):
        with patch("api.routers.period.parent_service_p") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Invalid invite code")
            resp = client.post("/period/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 404

    @pytest.mark.api
    def test_accept_invite_other_value_error_returns_400(self, client):
        with patch("api.routers.period.parent_service_p") as mock_parent:
            mock_parent.accept_invite.side_effect = ValueError("Something else went wrong")
            resp = client.post("/period/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 400

    @pytest.mark.api
    def test_accept_invite_exception_returns_500(self, client):
        with patch("api.routers.period.parent_service_p") as mock_parent:
            mock_parent.accept_invite.side_effect = RuntimeError("crash")
            resp = client.post("/period/accept-parent-invite", json={"code": "ABCD1234"})
        assert resp.status_code == 500


class TestCreatePeriod:

    @pytest.mark.api
    def test_create_period_teacher_with_pilot_access_returns_201(self, client):
        mock_vs = MagicMock()
        mock_vs.id = "vs-1"
        with patch("api.routers.period.teacher_dao_p") as mock_td, \
             patch("api.routers.period.append_canvas_file"), \
             patch("api.routers.period.create_vector_store") as mock_cvs, \
             patch("api.routers.period.upload_period_files", return_value=[]) as _mock_up, \
             patch("api.routers.period.try_generate_schedule", return_value={"schedule": {}}) as _mock_sched, \
             patch("api.routers.period.period_management_service") as mock_pms:
            mock_td.get_teacher_by_id.return_value = APPROVED_TEACHER
            mock_cvs.return_value = (mock_vs, [])
            mock_pms.create_period.return_value = {"period_id": "P1-ABCD-1234", "name": "Math 101"}
            resp = client.post("/period/create-period", data={"name": "Math 101"}, files=[])
        assert resp.status_code == 201
        assert "message" in resp.json()
        assert "period" in resp.json()

    @pytest.mark.api
    def test_create_period_teacher_without_pilot_access_returns_403(self, client):
        with patch.dict(os.environ, {"PILOT_WAITLIST_ENABLED": "true"}), \
             patch("api.routers.period.teacher_dao_p") as mock_td, \
             patch("api.routers.period.waitlist_service_p") as mock_wl:
            mock_td.get_teacher_by_id.return_value = UNAPPROVED_TEACHER
            mock_wl.get_status.return_value = {"on_waitlist": False}
            resp = client.post("/period/create-period", data={"name": "Math 101"}, files=[])
        assert resp.status_code == 403

    @pytest.mark.api
    def test_create_period_missing_name_returns_422(self, client):
        resp = client.post("/period/create-period", data={}, files=[])
        assert resp.status_code == 422

    @pytest.mark.api
    def test_create_period_exception_returns_500(self, client):
        mock_vs = MagicMock()
        mock_vs.id = "vs-1"
        with patch("api.routers.period.teacher_dao_p") as mock_td, \
             patch("api.routers.period.append_canvas_file"), \
             patch("api.routers.period.create_vector_store") as mock_cvs:
            mock_td.get_teacher_by_id.return_value = APPROVED_TEACHER
            mock_cvs.side_effect = RuntimeError("vector store failed")
            resp = client.post("/period/create-period", data={"name": "Math 101"}, files=[])
        assert resp.status_code == 500


class TestGetFilePresignedUrl:

    @pytest.mark.api
    def test_get_file_presigned_url_success(self, client):
        with patch("api.routers.period.get_file_presigned_url",
                   return_value="https://s3.amazonaws.com/bucket/file.pdf") as mock_fn:
            resp = client.get("/period/get-file/periods/p1/students/s1/file.pdf")
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://s3.amazonaws.com/bucket/file.pdf"
        mock_fn.assert_called_once_with("periods/p1/students/s1/file.pdf")

    @pytest.mark.api
    def test_get_file_presigned_url_exception_returns_500(self, client):
        with patch("api.routers.period.get_file_presigned_url") as mock_fn:
            mock_fn.side_effect = RuntimeError("S3 error")
            resp = client.get("/period/get-file/periods/p1/file.pdf")
        assert resp.status_code == 500


class TestAddFilesToPeriod:

    @pytest.mark.api
    def test_add_files_success(self, client):
        with patch("api.routers.period.period_management_service") as mock_pms, \
             patch("api.routers.period.upload_period_files",
                   return_value=["https://s3.example.com/f1.pdf"]) as _mock_up:
            mock_pms.period_dao.get_period_by_id.return_value = OWNED_PERIOD
            resp = client.post(
                "/period/add-files-to-period",
                data={"period_id": "p1"},
                files=[("files", ("test.txt", b"file content", "text/plain"))],
            )
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_add_files_period_not_found_returns_404(self, client):
        with patch("api.routers.period.period_management_service") as mock_pms:
            mock_pms.period_dao.get_period_by_id.return_value = None
            resp = client.post(
                "/period/add-files-to-period",
                data={"period_id": "missing"},
                files=[("files", ("f.txt", b"x", "text/plain"))],
            )
        assert resp.status_code == 404

    @pytest.mark.api
    def test_add_files_not_owner_returns_403(self, client):
        with patch("api.routers.period.period_management_service") as mock_pms:
            mock_pms.period_dao.get_period_by_id.return_value = OTHER_PERIOD
            resp = client.post(
                "/period/add-files-to-period",
                data={"period_id": "p1"},
                files=[("files", ("f.txt", b"x", "text/plain"))],
            )
        assert resp.status_code == 403

    @pytest.mark.api
    def test_add_files_service_error_returns_500(self, client):
        with patch("api.routers.period.period_management_service") as mock_pms, \
             patch("api.routers.period.upload_period_files") as mock_up:
            mock_pms.period_dao.get_period_by_id.return_value = OWNED_PERIOD
            mock_up.side_effect = RuntimeError("upload failed")
            resp = client.post(
                "/period/add-files-to-period",
                data={"period_id": "p1"},
                files=[("files", ("f.txt", b"x", "text/plain"))],
            )
        assert resp.status_code == 500


class TestUnenrollRoute:

    @pytest.mark.api
    @patch("api.routers.period.period_service")
    def test_unenroll_endpoint_success(self, mock_service: MagicMock, client) -> None:
        mock_service.unenroll_from_period.return_value = {
            "message": "Successfully unenrolled from period MATH-101",
            "period_id": "MATH-101",
            "remaining_enrollments": [],
        }
        resp = client.post("/period/unenroll", json={"period_id": "MATH-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_id"] == "MATH-101"

    @pytest.mark.api
    @patch("api.routers.period.period_service")
    def test_unenroll_endpoint_missing_period(self, mock_service: MagicMock, client) -> None:
        resp = client.post("/period/unenroll", json={})
        assert resp.status_code == 422

    @pytest.mark.api
    @patch("api.routers.period.period_service")
    def test_unenroll_endpoint_not_enrolled(self, mock_service: MagicMock, client) -> None:
        from exceptions.validation_error import ValidationError
        mock_service.unenroll_from_period.side_effect = ValidationError("You are not enrolled in period X")
        resp = client.post("/period/unenroll", json={"period_id": "X"})
        assert resp.status_code == 400
