from event_chatbot.core.config import Settings


def test_settings_accept_documented_api_key_names(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("TICKETMASTER_API_KEY", "ticketmaster-key")

    settings = Settings(_env_file=None)

    assert settings.openai_api_key == "openai-key"
    assert settings.ticketmaster_api_key == "ticketmaster-key"


def test_settings_accept_existing_api_key_aliases(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_AI_API_KEY", "open-ai-key")
    monkeypatch.setenv("TICKET_MASTER_CONSUMER_KEY", "ticket-master-key")

    settings = Settings(_env_file=None)

    assert settings.openai_api_key == "open-ai-key"
    assert settings.ticketmaster_api_key == "ticket-master-key"
