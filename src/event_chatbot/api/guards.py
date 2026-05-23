from fastapi import HTTPException

from event_chatbot.core.config import Settings


def require_non_production(settings: Settings, feature_name: str) -> None:
    if settings.app_env.casefold() == "production":
        raise HTTPException(
            status_code=404,
            detail=f"{feature_name} is disabled in production.",
        )
