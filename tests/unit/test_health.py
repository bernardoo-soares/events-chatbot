from fastapi.testclient import TestClient

from event_chatbot.main import create_app


def test_create_app_registers_health_route() -> None:
    app = create_app()

    routes = {route.path for route in app.routes}

    assert "/health" in routes


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
