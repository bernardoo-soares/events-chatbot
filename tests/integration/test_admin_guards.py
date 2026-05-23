from fastapi.testclient import TestClient

from event_chatbot.api.dependencies import get_settings
from event_chatbot.core.config import Settings
from event_chatbot.main import create_app


def test_ingest_endpoint_is_disabled_in_production() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="production", _env_file=None)
    client = TestClient(app)

    response = client.post("/ingest", json={"source": "agendalx", "city": "Lisbon", "size": 1})

    assert response.status_code == 404


def test_embedding_backfill_endpoint_is_disabled_in_production() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="production", _env_file=None)
    client = TestClient(app)

    response = client.post("/embeddings/backfill", json={"limit": 1})

    assert response.status_code == 404
