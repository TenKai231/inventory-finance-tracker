import pytest
from flask import Flask
from flask.testing import FlaskClient
from app import create_app

@pytest.fixture
def app() -> Flask:
    app_instance = create_app()
    app_instance.config["TESTING"] = True
    return app_instance

@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()

def test_dashboard_route(client: FlaskClient):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Welcome to the Dashboard" in response.data
