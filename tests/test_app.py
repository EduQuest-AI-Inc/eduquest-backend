"""
Basic tests for Flask application
These tests will run during CI pipeline
"""

import pytest
from app import app as flask_app


@pytest.fixture
def app():
    """Create application for testing"""
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.mark.smoke
def test_helloworld_endpoint(client):
    """Test the helloworld endpoint"""
    response = client.get('/helloworld')
    assert response.status_code == 200
    assert response.data == b'helloworld'


@pytest.mark.unit
def test_app_exists(app):
    """Test that app exists"""
    assert app is not None


@pytest.mark.unit
def test_app_is_testing(app):
    """Test that app is in testing mode"""
    assert app.config['TESTING'] is True


@pytest.mark.api
def test_cors_headers(client):
    """Test CORS headers are present"""
    response = client.get('/helloworld')
    # CORS headers should be set by Flask-CORS
    assert response.status_code == 200


@pytest.mark.api
def test_invalid_route(client):
    """Test invalid route returns 404"""
    response = client.get('/this-route-does-not-exist')
    assert response.status_code == 404


@pytest.mark.unit
def test_jwt_config(app):
    """Test JWT configuration is set"""
    assert 'JWT_SECRET_KEY' in app.config
    assert app.config['JWT_SECRET_KEY'] is not None
