from importlib.resources import files

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from event_chatbot.api.routers.chat import router as chat_router
from event_chatbot.api.routers.debug import router as debug_router
from event_chatbot.api.routers.events import router as events_router
from event_chatbot.api.routers.health import router as health_router
from event_chatbot.api.routers.ingest import router as ingest_router

WEB_DIR = files("event_chatbot").joinpath("web")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Event Chatbot",
        description="Grounded local event-discovery chatbot API.",
        version="0.1.0",
    )
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
    app.include_router(health_router)
    app.include_router(debug_router)
    app.include_router(ingest_router)
    app.include_router(events_router)
    app.include_router(chat_router)

    @app.get("/", include_in_schema=False)
    def web_app() -> FileResponse:
        return FileResponse(str(WEB_DIR.joinpath("index.html")))

    return app


app = create_app()
