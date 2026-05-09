"""Tests for the signup trial-confirmation gate.

Parents/teachers must explicitly confirm starting their 14-day no-card trial
before signup proceeds. Students never see this gate.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.api
@patch("routers.auth.user_dao")
def test_teacher_signup_without_trial_confirmation_is_rejected(mock_user_dao, client):
    mock_user_dao.get_by_email.return_value = None
    resp = client.post("/auth/signup", json={
        "username": "teacher_x",
        "password": "SecurePass1",
        "role": "teacher",
        "first_name": "T",
        "last_name": "Acher",
        "email": "t@eduquestai.org",
    })
    assert resp.status_code == 400
    assert "trial_confirmed" in resp.text


@pytest.mark.api
@patch("services.billing.membership_service.MembershipService.start_trial_if_eligible")
@patch("routers.auth.register_user", return_value={"success": True})
@patch("routers.auth.user_dao")
def test_teacher_signup_with_confirmation_starts_trial(
    mock_user_dao, mock_register, mock_start, client,
):
    mock_user_dao.get_by_email.return_value = None
    resp = client.post("/auth/signup", json={
        "username": "teacher_x",
        "password": "SecurePass1",
        "role": "teacher",
        "first_name": "T",
        "last_name": "Acher",
        "email": "t@eduquestai.org",
        "trial_confirmed": True,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body.get("trial_started") is True
    mock_start.assert_called_once_with("teacher_x", "teacher")


@pytest.mark.api
@patch("services.billing.membership_service.MembershipService.start_trial_if_eligible")
@patch("routers.auth.register_user", return_value={"success": True})
@patch("routers.auth.user_dao")
def test_student_signup_does_not_require_trial_confirmation(
    mock_user_dao, mock_register, mock_start, client,
):
    mock_user_dao.get_by_email.return_value = None
    resp = client.post("/auth/signup", json={
        "username": "stu1",
        "password": "SecurePass1",
        "role": "student",
        "first_name": "S",
        "last_name": "Tudent",
        "email": "s@eduquestai.org",
        "grade": "10",
    })
    assert resp.status_code == 201
    mock_start.assert_not_called()
