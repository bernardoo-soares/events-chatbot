import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException

from event_chatbot.core.config import Settings, get_settings
from event_chatbot.core.time import utc_now
from event_chatbot.db.connection import connect
from event_chatbot.db.migrations import initialize_database
from event_chatbot.providers.agno_llm import AgnoIntentExtractor, AgnoResponseRenderer
from event_chatbot.providers.llm import IntentExtractor, ResponseRenderer
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.services.chat_service import ChatService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_db_connection(settings: SettingsDep) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.database_path)
    initialize_database(conn)
    try:
        yield conn
    finally:
        conn.close()


def get_retrieval_service(
    settings: SettingsDep,
    conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
) -> RetrievalService:
    return RetrievalService(
        event_repository=EventRepository(conn),
        clock=utc_now,
        default_timezone=settings.default_timezone,
        default_days=settings.ingest_default_days,
    )


def get_intent_extractor(settings: SettingsDep) -> IntentExtractor:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for chat")
    return AgnoIntentExtractor(model_id=settings.openai_model, api_key=settings.openai_api_key)


def get_response_renderer(settings: SettingsDep) -> ResponseRenderer:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for chat")
    return AgnoResponseRenderer(model_id=settings.openai_model, api_key=settings.openai_api_key)


def get_chat_service(
    conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
    intent_extractor: Annotated[IntentExtractor, Depends(get_intent_extractor)],
    response_renderer: Annotated[ResponseRenderer, Depends(get_response_renderer)],
    retrieval: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> ChatService:
    return ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        intent_extractor=intent_extractor,
        response_renderer=response_renderer,
        retrieval=retrieval,
    )
