import sqlite3
from pathlib import Path

from fastapi import APIRouter
from openai import OpenAI

from event_chatbot.api.dependencies import SettingsDep
from event_chatbot.api.guards import require_non_production
from event_chatbot.core.logging import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/llm")
def llm_health(settings: SettingsDep) -> dict:
    require_non_production(settings, "LLM health diagnostics")
    logger.info(
        "Checking LLM health model=%s key_loaded=%s",
        settings.openai_model,
        bool(settings.openai_api_key),
    )
    result = {
        "openai_key_loaded": bool(settings.openai_api_key),
        "openai_model": settings.openai_model,
        "openai_connection": "not_checked",
        "error_type": None,
        "error_message": None,
    }
    if not settings.openai_api_key:
        result["openai_connection"] = "missing_key"
        logger.warning("LLM health check skipped because OPENAI_API_KEY is missing")
        return result

    try:
        client = OpenAI(api_key=settings.openai_api_key, timeout=20.0, max_retries=0)
        response = client.responses.create(
            model=settings.openai_model,
            input="Return exactly: ok",
            max_output_tokens=16,
        )
        result["openai_connection"] = "ok"
        result["sample_output"] = getattr(response, "output_text", None)
        logger.info("LLM health check succeeded model=%s", settings.openai_model)
    except Exception as exc:
        result["openai_connection"] = "failed"
        result["error_type"] = type(exc).__name__
        result["error_message"] = str(exc)
        logger.exception("LLM health check failed model=%s", settings.openai_model)
    return result


@router.get("/db")
def db_health(settings: SettingsDep) -> dict:
    path = Path(settings.database_path)
    result: dict[str, object] = {
        "database_path": settings.database_path,
        "file_exists": path.exists(),
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
        "event_count": None,
        "city_counts": {},
        "error_type": None,
        "error_message": None,
    }
    logger.info(
        "Checking DB health path=%s file_exists=%s",
        settings.database_path,
        path.exists(),
    )
    if not path.exists():
        logger.warning("DB health check found missing database path=%s", settings.database_path)
        return result

    try:
        conn = sqlite3.connect(settings.database_path)
        conn.row_factory = sqlite3.Row
        event_count = conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
        city_rows = conn.execute(
            """
            SELECT city, COUNT(*) AS count
            FROM events
            GROUP BY city
            ORDER BY count DESC, city ASC
            """
        ).fetchall()
        conn.close()
        result["event_count"] = event_count
        result["city_counts"] = {
            row["city"] or "Unknown": row["count"]
            for row in city_rows
        }
        logger.info(
            "DB health check succeeded path=%s event_count=%s city_counts=%s",
            settings.database_path,
            result["event_count"],
            result["city_counts"],
        )
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error_message"] = str(exc)
        logger.exception("DB health check failed path=%s", settings.database_path)
    return result
