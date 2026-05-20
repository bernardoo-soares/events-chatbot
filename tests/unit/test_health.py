from event_chatbot.main import create_app


def test_create_app_registers_health_route() -> None:
    app = create_app()

    routes = {route.path for route in app.routes}

    assert "/health" in routes

