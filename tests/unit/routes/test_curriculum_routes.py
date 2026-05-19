import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_auth, get_period, AuthPayload, Role
from routers.curriculum import _get_curriculum_service, _get_slides_service, _membership_or_summer
from exceptions.not_found_error import NotFoundError

_PERIOD_ID = "period-1"
_OWNED_PERIOD = {"period_id": _PERIOD_ID, "owner_id": "user-1"}

_TEACHER_AUTH = AuthPayload(sub="user-1", role=Role.TEACHER, token="fake-token")


def _deny_membership():
    raise HTTPException(
        status_code=403,
        detail={"error": "Active membership required", "code": "MEMBERSHIP_REQUIRED"},
    )


def _period_not_found():
    raise HTTPException(status_code=404, detail=f"Period '{_PERIOD_ID}' not found")


@pytest.fixture
def client():
    app.dependency_overrides[get_auth] = lambda: _TEACHER_AUTH
    app.dependency_overrides[_membership_or_summer] = lambda: _TEACHER_AUTH
    app.dependency_overrides[get_period] = lambda: _OWNED_PERIOD
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def membership_denied_client():
    app.dependency_overrides[get_auth] = lambda: _TEACHER_AUTH
    app.dependency_overrides[_membership_or_summer] = _deny_membership
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestGenerateCurriculum:

    @pytest.mark.api
    def test_generate_success_returns_202(self, client):
        mock_cs = MagicMock()
        mock_cs.trigger_generation.return_value = None
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.post(f"/curriculum/{_PERIOD_ID}/generate")
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 202
        assert "message" in resp.json()

    @pytest.mark.api
    def test_generate_membership_denied_returns_403(self, membership_denied_client):
        resp = membership_denied_client.post(f"/curriculum/{_PERIOD_ID}/generate")
        assert resp.status_code == 403

    @pytest.mark.api
    def test_generate_period_not_found_returns_404(self, client):
        app.dependency_overrides[get_period] = _period_not_found
        resp = client.post(f"/curriculum/{_PERIOD_ID}/generate")
        app.dependency_overrides[get_period] = lambda: _OWNED_PERIOD
        assert resp.status_code == 404


class TestGetCurriculum:

    @pytest.mark.api
    def test_get_curriculum_success_returns_200(self, client):
        curriculum_data = {"weeks": [], "lessons": [], "concepts": [], "skills": []}
        mock_cs = MagicMock()
        mock_cs.get_curriculum.return_value = curriculum_data
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.get(f"/curriculum/{_PERIOD_ID}")
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 200
        body = resp.json()
        assert "weeks" in body

    @pytest.mark.api
    def test_get_curriculum_not_found_returns_404(self, client):
        mock_cs = MagicMock()
        mock_cs.get_curriculum.side_effect = NotFoundError("not found")
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.get(f"/curriculum/{_PERIOD_ID}")
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 404


class TestSaveCurriculum:

    @pytest.mark.api
    def test_save_curriculum_success_returns_200(self, client):
        mock_cs = MagicMock()
        mock_cs.save_curriculum.return_value = None
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.patch(
            f"/curriculum/{_PERIOD_ID}",
            json={"weeks": [], "lessons": [], "concepts": [], "skills": [], "concept_skills": []},
        )
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestUpdateConcept:

    @pytest.mark.api
    def test_update_concept_success_returns_200(self, client):
        mock_cs = MagicMock()
        mock_cs.update_concept.return_value = None
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.patch(
            f"/curriculum/{_PERIOD_ID}/concepts/algebra",
            json={"description": "Updated description"},
        )
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_update_concept_not_found_returns_404(self, client):
        mock_cs = MagicMock()
        mock_cs.update_concept.side_effect = NotFoundError("concept not found")
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.patch(
            f"/curriculum/{_PERIOD_ID}/concepts/nonexistent",
            json={},
        )
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 404


class TestUpdateSkill:

    @pytest.mark.api
    def test_update_skill_success_returns_200(self, client):
        mock_cs = MagicMock()
        mock_cs.update_skill.return_value = None
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.patch(
            f"/curriculum/{_PERIOD_ID}/skills/multiplication",
            json={"description": "Updated skill"},
        )
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.api
    def test_update_skill_not_found_returns_404(self, client):
        mock_cs = MagicMock()
        mock_cs.update_skill.side_effect = NotFoundError("skill not found")
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        resp = client.patch(
            f"/curriculum/{_PERIOD_ID}/skills/nonexistent",
            json={},
        )
        app.dependency_overrides.pop(_get_curriculum_service, None)
        assert resp.status_code == 404


class TestApprovePeriod:

    @pytest.mark.api
    def test_approve_period_success_returns_202(self, client):
        mock_cs = MagicMock()
        mock_cs.approve_period.return_value = [{"lesson_id": "l1", "lesson_name": "Intro"}]
        mock_ss = MagicMock()
        app.dependency_overrides[_get_curriculum_service] = lambda: mock_cs
        app.dependency_overrides[_get_slides_service] = lambda: mock_ss
        resp = client.post(f"/curriculum/{_PERIOD_ID}/approve")
        app.dependency_overrides.pop(_get_curriculum_service, None)
        app.dependency_overrides.pop(_get_slides_service, None)
        assert resp.status_code == 202

    @pytest.mark.api
    def test_approve_period_membership_denied_returns_403(self, membership_denied_client):
        resp = membership_denied_client.post(f"/curriculum/{_PERIOD_ID}/approve")
        assert resp.status_code == 403
