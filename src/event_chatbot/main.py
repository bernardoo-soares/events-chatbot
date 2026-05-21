from importlib.resources import files
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from event_chatbot.api.routers.chat import router as chat_router
from event_chatbot.api.routers.debug import router as debug_router
from event_chatbot.api.routers.events import router as events_router
from event_chatbot.api.routers.health import router as health_router
from event_chatbot.api.routers.ingest import router as ingest_router
from event_chatbot.core.logging import configure_logging, get_logger

WEB_DIR = files("event_chatbot").joinpath("web")
logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    logger.info("Creating FastAPI app")
    app = FastAPI(
        title="Event Chatbot",
        description="Grounded local event-discovery chatbot API.",
        version="0.1.0",
    )
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
    logger.info("Mounted static web assets path=%s", WEB_DIR)
    app.include_router(health_router)
    app.include_router(debug_router)
    app.include_router(ingest_router)
    app.include_router(events_router)
    app.include_router(chat_router)
    logger.info("Registered API routers")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (perf_counter() - started_at) * 1000
            logger.exception(
                "HTTP request failed method=%s path=%s elapsed_ms=%.2f",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise
        elapsed_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "HTTP request completed method=%s path=%s status=%s elapsed_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @app.get("/", include_in_schema=False)
    def web_app() -> FileResponse:
        logger.debug("Serving web app")
        return FileResponse(str(WEB_DIR.joinpath("index.html")))

    return app


app = create_app()
