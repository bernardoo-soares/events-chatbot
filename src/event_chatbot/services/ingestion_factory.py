import sqlite3

from fastapi import HTTPException

from event_chatbot.core.config import Settings
from event_chatbot.core.time import utc_now
from event_chatbot.providers.agendalx import AgendaLXProvider, normalize_agendalx_event
from event_chatbot.providers.ticketmaster import (
    TicketmasterProvider,
    normalize_ticketmaster_event,
)
from event_chatbot.services.ingestion_service import IngestionService
from event_chatbot.types.ingestion import IngestionSource


def build_ingestion_service(
    source: IngestionSource,
    conn: sqlite3.Connection,
    settings: Settings,
) -> IngestionService:
    if source == "ticketmaster":
        if not settings.ticketmaster_api_key:
            raise HTTPException(
                status_code=503,
                detail="TICKETMASTER_API_KEY is required for Ticketmaster ingestion",
            )
        return IngestionService(
            conn=conn,
            provider=TicketmasterProvider(
                api_key=settings.ticketmaster_api_key,
                base_url=settings.ticketmaster_base_url,
            ),
            normalizer=normalize_ticketmaster_event,
            clock=utc_now,
        )

    if source == "agendalx":
        return IngestionService(
            conn=conn,
            provider=AgendaLXProvider(
                base_url=settings.agendalx_base_url,
                per_page=settings.agendalx_per_page,
            ),
            normalizer=normalize_agendalx_event,
            clock=utc_now,
        )

    raise HTTPException(status_code=400, detail=f"Unsupported ingestion source: {source}")
