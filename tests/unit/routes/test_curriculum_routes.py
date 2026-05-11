import pytest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, require_active_membership, AuthPayload, Role
from exceptions.not_found_error import NotFoundError

_PERIOD_ID = "period-1"
_OWNED_PERIOD = {"period_id": _PERIOD_ID, "owner_id": "user-1"}

_TEACHER_AUTH = AuthPayload(sub="user-1", role=Role.TEACHER, token="fake-token")


def _deny_membership():
    raise HTTPException(
        status_code=403,
        detail={"error": "Active membership required", "code": "MEMBERSHIP_REQUIRED"},
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: _TEACHER_AUTH
    app.dependency_overrides[require_active_membership] = lambda: _TEACHER_AUTH
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def membership_denied_client():
    app.dependency_overrides[get_auth] = lambda: _TEACHER_AUTH
    app.dependency_overrides[require_active_membership] = _deny_membership
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestGenerateCurriculum:

    @pytest.mark.api
    def test_generate_success_returns_202(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.trigger_generation.return_value = None
            resp = client.post(f"/curriculum/{_PERIOD_ID}/generate")
        assert resp.status_code == 202
        assert "message" in resp.json()

    @pytest.mark.api
    def test_generate_membership_denied_returns_403(self, membership_denied_client):
        resp = membership_denied_client.post(f"/curriculum/{_PERIOD_ID}/generate")
        assert resp.status_code == 403

    @pytest.mark.api
    def test_generate_period_not_found_returns_404(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao:
            mock_dao.get_period_by_id.return_value = None
            resp = client.post(f"/curriculum/{_PERIOD_ID}/generate")
        assert resp.status_code == 404


class TestGetCurriculum:

    @pytest.mark.api
    def test_get_curriculum_success_returns_200(self, client):
        curriculum_data = {"weeks": [], "lessons": [], "concepts": [], "skills": []}
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.get_curriculum.return_value = curriculum_data
            resp = client.get(f"/curriculum/{_PERIOD_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert "weeks" in body

    @pytest.mark.api
    def test_get_curriculum_not_found_returns_404(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.get_curriculum.side_effect = NotFoundError("not found")
            resp = client.get(f"/curriculum/{_PERIOD_ID}")
        assert resp.status_code == 404


class TestSaveCurriculum:

    @pytest.mark.api
    def test_save_curriculum_success_returns_200(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.save_curriculum.return_value = None
            resp = client.patch(
                f"/curriculum/{_PERIOD_ID}",
                json={"weeks": [], "lessons": [], "concepts": [], "skills": [], "concept_skills": []},
            )
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestUpdateConcept:

    @pytest.mark.api
    def test_update_concept_success_returns_200(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.update_concept.return_value = None
            resp = client.patch(
                f"/curriculum/{_PERIOD_ID}/concepts/algebra",
                json={"description": "Updated description"},
            )
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_update_concept_not_found_returns_404(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.update_concept.side_effect = NotFoundError("concept not found")
            resp = client.patch(
                f"/curriculum/{_PERIOD_ID}/concepts/nonexistent",
                json={},
            )
        assert resp.status_code == 404


class TestUpdateSkill:

    @pytest.mark.api
    def test_update_skill_success_returns_200(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.update_skill.return_value = None
            resp = client.patch(
                f"/curriculum/{_PERIOD_ID}/skills/multiplication",
                json={"description": "Updated skill"},
            )
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_update_skill_not_found_returns_404(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.update_skill.side_effect = NotFoundError("skill not found")
            resp = client.patch(
                f"/curriculum/{_PERIOD_ID}/skills/nonexistent",
                json={},
            )
        assert resp.status_code == 404


class TestApprovePeriod:

    @pytest.mark.api
    def test_approve_period_success_returns_200(self, client):
        with patch("routers.curriculum._period_dao") as mock_dao, \
             patch("routers.curriculum._curriculum_service") as mock_cs:
            mock_dao.get_period_by_id.return_value = _OWNED_PERIOD
            mock_cs.approve_period.return_value = None
            resp = client.post(f"/curriculum/{_PERIOD_ID}/approve")
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_approve_period_membership_denied_returns_403(self, membership_denied_client):
        resp = membership_denied_client.post(f"/curriculum/{_PERIOD_ID}/approve")
        assert resp.status_code == 403
