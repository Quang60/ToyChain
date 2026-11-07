import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def settings(node="DONG"):
    return Settings(node=node, database_url="sqlite:///:memory:", jwt_secret="test-secret-" * 4, internal_secret="test-internal-" * 3, demo_password="TestPassword2026!", test_mode=True)


def auth(client, username="admin"):
    response = client.post("/api/auth/login", json={"username": username, "password": "TestPassword2026!"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def branch():
    app = create_app(settings())
    with TestClient(app) as client:
        yield client, app, auth(client)


@pytest.fixture
def central():
    app = create_app(settings("CENTRAL"))
    with TestClient(app) as client:
        yield client, app, auth(client)
