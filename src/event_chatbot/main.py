from fastapi import FastAPI

from event_chatbot.api.routers.chat import router as chat_router
from event_chatbot.api.routers.events import router as events_router
from event_chatbot.api.routers.health import router as health_router
from event_chatbot.api.routers.ingest import router as ingest_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Event Chatbot",
        description="Grounded local event-discovery chatbot API.",
        version="0.1.0",
    )
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(events_router)
    app.include_router(chat_router)
    return app


app = create_app()
