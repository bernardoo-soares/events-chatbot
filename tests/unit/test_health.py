from fastapi.testclient import TestClient

from event_chatbot.api.dependencies import get_settings
from event_chatbot.core.config import Settings
from event_chatbot.main import create_app


def test_create_app_registers_health_route() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_web_app_is_served_at_root() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Find your next unforgettable night out" in response.text


def test_static_app_assets_are_served() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert app_response.status_code == 200
    assert css_response.status_code == 200
    assert "I'm thinking" in app_response.text


def test_llm_health_reports_missing_key() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    client = TestClient(app)

    response = client.get("/health/llm")

    assert response.status_code == 200
    body = response.json()
    assert body["openai_key_loaded"] is False
    assert body["openai_connection"] == "missing_key"
    assert "openai_key_prefix" not in body
    assert "openai_key_length" not in body


def test_llm_health_is_disabled_in_production() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="production", _env_file=None)
    client = TestClient(app)

    response = client.get("/health/llm")

    assert response.status_code == 404
