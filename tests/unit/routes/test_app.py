"""
Basic smoke tests for the FastAPI application.
"""
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.smoke
def test_helloworld_endpoint(client):
    response = client.get("/helloworld")
    assert response.status_code == 200
    assert response.json() == "helloworld"


@pytest.mark.unit
def test_app_exists():
    assert app is not None


@pytest.mark.api
def test_invalid_route(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
