from fastapi import APIRouter
from openai import OpenAI

from event_chatbot.api.dependencies import SettingsDep

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/llm")
def llm_health(settings: SettingsDep) -> dict:
    result = {
        "openai_key_loaded": bool(settings.openai_api_key),
        "openai_key_length": len(settings.openai_api_key or ""),
        "openai_key_prefix": _safe_key_prefix(settings.openai_api_key),
        "openai_model": settings.openai_model,
        "openai_connection": "not_checked",
        "error_type": None,
        "error_message": None,
    }
    if not settings.openai_api_key:
        result["openai_connection"] = "missing_key"
        return result

    try:
        client = OpenAI(api_key=settings.openai_api_key, timeout=20.0, max_retries=0)
        response = client.responses.create(
            model=settings.openai_model,
            input="Return exactly: ok",
            max_output_tokens=8,
        )
        result["openai_connection"] = "ok"
        result["sample_output"] = getattr(response, "output_text", None)
    except Exception as exc:
        result["openai_connection"] = "failed"
        result["error_type"] = type(exc).__name__
        result["error_message"] = str(exc)
    return result


def _safe_key_prefix(value: str | None) -> str | None:
    if not value:
        return None
    return f"{value[:7]}..."
