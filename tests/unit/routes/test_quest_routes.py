import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, AuthPayload

_QUEST = {
    "quest_id": "q1",
    "user_id": "user-1",
    "period_id": "p1",
    "description": "Algebra",
    "skills": "arithmetic",
    "week": 1,
    "rubric": {},
    "instructions": [],
    "status": "not_started",
    "completed_steps": [],
}


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="user-1", role="student", token="fake-token"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def teacher_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="teacher-1", role="teacher", token="t"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def other_teacher_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="teacher-2", role="teacher", token="t"
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestGetQuests:

    @pytest.mark.api
    def test_get_quests_no_period_id_calls_get_all(self, client):
        mock_svc = MagicMock()
        mock_svc.get_quests_for_student.return_value = [_QUEST]
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = client.get("/quest/quests")
        assert resp.status_code == 200
        assert resp.json()[0]["quest_id"] == "q1"
        mock_svc.get_quests_for_student.assert_called_once_with("user-1")
        mock_svc.get_quests_for_student_and_period.assert_not_called()

    @pytest.mark.api
    def test_get_quests_with_period_id_calls_period_filtered(self, client):
        quest_p1 = {**_QUEST, "quest_id": "q2"}
        mock_svc = MagicMock()
        mock_svc.get_quests_for_student_and_period.return_value = [quest_p1]
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = client.get("/quest/quests", params={"period_id": "p1"})
        assert resp.status_code == 200
        mock_svc.get_quests_for_student_and_period.assert_called_once_with("user-1", "p1")
        mock_svc.get_quests_for_student.assert_not_called()

    @pytest.mark.api
    def test_get_quests_service_error_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.get_quests_for_student.side_effect = RuntimeError("crash")
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = client.get("/quest/quests")
        assert resp.status_code == 500


class TestGetQuestById:

    @pytest.mark.api
    def test_get_quest_by_id_found(self, client):
        mock_svc = MagicMock()
        mock_svc.get_quest_by_id.return_value = _QUEST
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = client.get("/quest/quests/q1")
        assert resp.status_code == 200
        assert resp.json()["quest_id"] == "q1"

    @pytest.mark.api
    def test_get_quest_by_id_not_found_returns_404(self, client):
        mock_svc = MagicMock()
        mock_svc.get_quest_by_id.return_value = None
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = client.get("/quest/quests/missing-id")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    @pytest.mark.api
    def test_get_quest_by_id_exception_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.get_quest_by_id.side_effect = RuntimeError("crash")
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc):
            resp = client.get("/quest/quests/q1")
        assert resp.status_code == 500


class TestGetStudentQuests:

    @pytest.mark.api
    def test_get_student_quests_same_user_skips_authorization(self, client):
        mock_svc = MagicMock()
        mock_svc.get_quests_for_student.return_value = [_QUEST]
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = client.get("/quest/quests/student/user-1")
        assert resp.status_code == 200
        mock_svc.get_quests_for_student.assert_called_once_with("user-1")

    @pytest.mark.api
    def test_get_student_quests_authorized_teacher(self, teacher_client):
        mock_enrollment = MagicMock()
        mock_enrollment.get_enrollments_by_student.return_value = [{"period_id": "p1"}]
        mock_period_mgmt = MagicMock()
        mock_period_mgmt.get_periods_by_owner.return_value = [{"period_id": "p1"}]
        mock_retrieval = MagicMock()
        mock_retrieval.get_quests_for_student.return_value = [{**_QUEST, "quest_id": "q3"}]
        with patch("routers.quest.EnrollmentService", return_value=mock_enrollment), \
             patch("routers.quest.PeriodManagementService", return_value=mock_period_mgmt), \
             patch("routers.quest.QuestRetrievalService", return_value=mock_retrieval), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = teacher_client.get("/quest/quests/student/student-1")
        assert resp.status_code == 200

    @pytest.mark.api
    def test_get_student_quests_unauthorized_returns_403(self, other_teacher_client):
        mock_enrollment = MagicMock()
        mock_enrollment.get_enrollments_by_student.return_value = [{"period_id": "p1"}]
        mock_period_mgmt = MagicMock()
        mock_period_mgmt.get_periods_by_owner.return_value = [{"period_id": "p99"}]
        with patch("routers.quest.EnrollmentService", return_value=mock_enrollment), \
             patch("routers.quest.PeriodManagementService", return_value=mock_period_mgmt):
            resp = other_teacher_client.get("/quest/quests/student/student-1")
        assert resp.status_code == 403

    @pytest.mark.api
    def test_get_student_quests_service_error_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.get_quests_for_student.side_effect = RuntimeError("crash")
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc), \
             patch("routers.quest.QuestRetrievalService.attach_grade_display"):
            resp = client.get("/quest/quests/student/user-1")
        assert resp.status_code == 500


class TestUpdateQuestStatus:

    @pytest.mark.api
    def test_update_quest_status_valid_status(self, client):
        mock_svc = MagicMock()
        mock_svc.update_quest_status.return_value = {
            "message": "Successfully updated quest q1 status to completed",
            "quest_id": "q1",
            "status": "completed",
        }
        with patch("routers.quest.QuestGradingService", return_value=mock_svc):
            resp = client.put("/quest/quests/q1/status", json={"status": "completed"})
        assert resp.status_code == 200

    @pytest.mark.api
    def test_update_quest_status_invalid_status_returns_400(self, client):
        resp = client.put("/quest/quests/q1/status", json={"status": "invalid_status"})
        assert resp.status_code == 400
        assert "detail" in resp.json()

    @pytest.mark.api
    def test_update_quest_status_service_error_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.update_quest_status.side_effect = RuntimeError("crash")
        with patch("routers.quest.QuestGradingService", return_value=mock_svc):
            resp = client.put("/quest/quests/q1/status", json={"status": "completed"})
        assert resp.status_code == 500


class TestGradeQuest:

    @pytest.mark.api
    def test_grade_quest_success(self, client):
        mock_svc = MagicMock()
        mock_svc.update_quest_grade_and_feedback.return_value = None
        with patch("routers.quest.QuestGradingService", return_value=mock_svc):
            resp = client.put(
                "/quest/quests/q1/grade",
                json={"grade": {"skill1": 0.8}, "feedback": "Good work"},
            )
        assert resp.status_code == 200
        assert "message" in resp.json()
        assert resp.json()["quest_id"] == "q1"

    @pytest.mark.api
    def test_grade_quest_missing_fields_returns_422(self, client):
        resp = client.put("/quest/quests/q1/grade", json={"grade": {"skill1": 0.8}})
        assert resp.status_code == 422

    @pytest.mark.api
    def test_grade_quest_service_error_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.update_quest_grade_and_feedback.side_effect = RuntimeError("crash")
        with patch("routers.quest.QuestGradingService", return_value=mock_svc):
            resp = client.put(
                "/quest/quests/q1/grade",
                json={"grade": {"skill1": 0.8}, "feedback": "Good work"},
            )
        assert resp.status_code == 500


class TestVerifyQuestStructure:

    @pytest.mark.api
    def test_verify_quest_structure_success(self, client):
        mock_svc = MagicMock()
        mock_svc.verify_quest_structure.return_value = {"is_valid": True, "missing_weeks": []}
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc):
            resp = client.get("/quest/verify-quest-structure/p1")
        assert resp.status_code == 200
        mock_svc.verify_quest_structure.assert_called_once_with("user-1", "p1")

    @pytest.mark.api
    def test_verify_quest_structure_exception_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.verify_quest_structure.side_effect = RuntimeError("crash")
        with patch("routers.quest.QuestRetrievalService", return_value=mock_svc):
            resp = client.get("/quest/verify-quest-structure/p1")
        assert resp.status_code == 500
