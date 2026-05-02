import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from api.deps import get_auth, AuthPayload


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="user-1", role="student", token="fake-token"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def teacher_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="teacher-1", role="teacher", token="t"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def other_teacher_client():
    app.dependency_overrides[get_auth] = lambda: AuthPayload(
        sub="teacher-2", role="teacher", token="t"
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestGetQuests:

    @pytest.mark.api
    def test_get_quests_no_period_id_calls_get_all(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_qs.get_quests_for_student.return_value = [{"quest_id": "q1", "description": "Algebra"}]
            resp = client.get("/quest/quests")
        assert resp.status_code == 200
        assert resp.json() == [{"quest_id": "q1", "description": "Algebra"}]
        mock_qs.get_quests_for_student.assert_called_once_with("user-1")
        mock_qs.get_quests_for_student_and_period.assert_not_called()

    @pytest.mark.api
    def test_get_quests_with_period_id_calls_period_filtered(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_qs.get_quests_for_student_and_period.return_value = [{"quest_id": "q2"}]
            resp = client.get("/quest/quests", params={"period_id": "p1"})
        assert resp.status_code == 200
        mock_qs.get_quests_for_student_and_period.assert_called_once_with("user-1", "p1")
        mock_qs.get_quests_for_student.assert_not_called()

    @pytest.mark.api
    def test_get_quests_service_error_returns_500(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_qs.get_quests_for_student.side_effect = RuntimeError("crash")
            resp = client.get("/quest/quests")
        assert resp.status_code == 500


class TestGetQuestById:

    @pytest.mark.api
    def test_get_quest_by_id_found(self, client):
        with patch("api.routers.quest.quest_dao") as mock_qd, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_qd.get_quest_by_id.return_value = {"quest_id": "q1", "description": "Algebra"}
            resp = client.get("/quest/quests/q1")
        assert resp.status_code == 200
        assert resp.json()["quest_id"] == "q1"

    @pytest.mark.api
    def test_get_quest_by_id_not_found_returns_404(self, client):
        with patch("api.routers.quest.quest_dao") as mock_qd, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_qd.get_quest_by_id.return_value = None
            resp = client.get("/quest/quests/missing-id")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    @pytest.mark.api
    def test_get_quest_by_id_exception_returns_500(self, client):
        with patch("api.routers.quest.quest_dao") as mock_qd:
            mock_qd.get_quest_by_id.side_effect = RuntimeError("crash")
            resp = client.get("/quest/quests/q1")
        assert resp.status_code == 500


class TestGetStudentQuests:

    @pytest.mark.api
    def test_get_student_quests_same_user_skips_authorization(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_qs.get_quests_for_student.return_value = [{"quest_id": "q1"}]
            resp = client.get("/quest/quests/student/user-1")
        assert resp.status_code == 200
        mock_qs.get_quests_for_student.assert_called_once_with("user-1")

    @pytest.mark.api
    def test_get_student_quests_authorized_teacher(self, teacher_client):
        with patch("api.routers.quest.enrollment_dao") as mock_ed, \
             patch("api.routers.quest.period_dao") as mock_pd, \
             patch("api.routers.quest.quest_service") as mock_qs, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_ed.get_enrollments_by_student.return_value = [{"period_id": "p1"}]
            mock_pd.get_periods_by_owner_id.return_value = [{"period_id": "p1"}]
            mock_qs.get_quests_for_student.return_value = [{"quest_id": "q3"}]
            resp = teacher_client.get("/quest/quests/student/student-1")
        assert resp.status_code == 200

    @pytest.mark.api
    def test_get_student_quests_unauthorized_returns_403(self, other_teacher_client):
        with patch("api.routers.quest.enrollment_dao") as mock_ed, \
             patch("api.routers.quest.period_dao") as mock_pd:
            mock_ed.get_enrollments_by_student.return_value = [{"period_id": "p1"}]
            mock_pd.get_periods_by_owner_id.return_value = [{"period_id": "p99"}]
            resp = other_teacher_client.get("/quest/quests/student/student-1")
        assert resp.status_code == 403

    @pytest.mark.api
    def test_get_student_quests_service_error_returns_500(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs, \
             patch("api.routers.quest.QuestRetrievalService.attach_grade_display"):
            mock_qs.get_quests_for_student.side_effect = RuntimeError("crash")
            resp = client.get("/quest/quests/student/user-1")
        assert resp.status_code == 500


class TestUpdateQuestStatus:

    @pytest.mark.api
    def test_update_quest_status_valid_status(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs:
            mock_qs.update_quest_status.return_value = {"quest_id": "q1", "status": "completed"}
            resp = client.put("/quest/quests/q1/status", json={"status": "completed"})
        assert resp.status_code == 200

    @pytest.mark.api
    def test_update_quest_status_invalid_status_returns_400(self, client):
        resp = client.put("/quest/quests/q1/status", json={"status": "invalid_status"})
        assert resp.status_code == 400
        assert "detail" in resp.json()

    @pytest.mark.api
    def test_update_quest_status_service_error_returns_500(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs:
            mock_qs.update_quest_status.side_effect = RuntimeError("crash")
            resp = client.put("/quest/quests/q1/status", json={"status": "completed"})
        assert resp.status_code == 500


class TestGradeQuest:

    @pytest.mark.api
    def test_grade_quest_success(self, client):
        with patch("api.routers.quest.quest_dao") as mock_qd:
            mock_qd.update_quest_grade_and_feedback.return_value = None
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
        with patch("api.routers.quest.quest_dao") as mock_qd:
            mock_qd.update_quest_grade_and_feedback.side_effect = RuntimeError("crash")
            resp = client.put(
                "/quest/quests/q1/grade",
                json={"grade": {"skill1": 0.8}, "feedback": "Good work"},
            )
        assert resp.status_code == 500


class TestVerifyQuestStructure:

    @pytest.mark.api
    def test_verify_quest_structure_success(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs:
            mock_qs.verify_quest_structure.return_value = {"is_valid": True, "missing_weeks": []}
            resp = client.get("/quest/verify-quest-structure/p1")
        assert resp.status_code == 200
        mock_qs.verify_quest_structure.assert_called_once_with("user-1", "p1")

    @pytest.mark.api
    def test_verify_quest_structure_exception_returns_500(self, client):
        with patch("api.routers.quest.quest_service") as mock_qs:
            mock_qs.verify_quest_structure.side_effect = RuntimeError("crash")
            resp = client.get("/quest/verify-quest-structure/p1")
        assert resp.status_code == 500
