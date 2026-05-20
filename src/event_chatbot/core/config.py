from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_path: str = "data/events.sqlite"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "OPEN_AI_API_KEY"),
    )
    openai_model: str = "gpt-4o-mini"
    ticketmaster_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TICKETMASTER_API_KEY", "TICKET_MASTER_CONSUMER_KEY"),
    )
    ticketmaster_base_url: str = "https://app.ticketmaster.com/discovery/v2"
    default_city: str = "Lisbon"
    default_timezone: str = "Europe/Lisbon"
    ingest_default_days: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
