import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException

from event_chatbot.core.config import Settings, get_settings
from event_chatbot.core.logging import get_logger
from event_chatbot.core.time import utc_now
from event_chatbot.db.connection import connect
from event_chatbot.db.migrations import initialize_database
from event_chatbot.providers.agno_llm import AgnoIntentExtractor
from event_chatbot.providers.embeddings import OpenAIEmbeddingProvider
from event_chatbot.providers.llm import IntentExtractor, RequestIntentClassifier, ResponseRenderer
from event_chatbot.providers.template_response import TemplateResponseRenderer
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.repositories.event_embeddings import EventEmbeddingRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.semantic import SemanticScorer
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.services.chat_service import ChatService

SettingsDep = Annotated[Settings, Depends(get_settings)]
logger = get_logger(__name__)


def get_db_connection(settings: SettingsDep) -> Iterator[sqlite3.Connection]:
    logger.debug("Creating request database connection path=%s", settings.database_path)
    conn = connect(settings.database_path)
    initialize_database(conn)
    try:
        yield conn
    finally:
        logger.debug("Closing request database connection path=%s", settings.database_path)
        conn.close()


def get_retrieval_service(
    settings: SettingsDep,
    conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
) -> RetrievalService:
    logger.debug(
        "Building retrieval service default_timezone=%s default_days=%s",
        settings.default_timezone,
        settings.ingest_default_days,
    )
    semantic_scorer = None
    if settings.semantic_ranking_enabled and settings.openai_api_key:
        semantic_scorer = SemanticScorer(
            embedding_repository=EventEmbeddingRepository(conn),
            embedding_provider=OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_embedding_model,
                batch_size=settings.embedding_batch_size,
            ),
        )
    return RetrievalService(
        event_repository=EventRepository(conn),
        clock=utc_now,
        default_timezone=settings.default_timezone,
        default_days=settings.ingest_default_days,
        semantic_scorer=semantic_scorer,
    )


def get_intent_extractor(settings: SettingsDep) -> IntentExtractor:
    if not settings.openai_api_key:
        logger.warning("Cannot build intent extractor because OPENAI_API_KEY is missing")
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for chat")
    logger.debug("Building Agno intent extractor model=%s", settings.openai_model)
    return AgnoIntentExtractor(model_id=settings.openai_model, api_key=settings.openai_api_key)


def get_request_intent_classifier(settings: SettingsDep) -> RequestIntentClassifier:
    if not settings.openai_api_key:
        logger.warning("Cannot build request-intent classifier because OPENAI_API_KEY is missing")
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for chat")
    logger.debug("Building Agno request-intent classifier model=%s", settings.openai_model)
    return AgnoIntentExtractor(model_id=settings.openai_model, api_key=settings.openai_api_key)


def get_response_renderer(settings: SettingsDep) -> ResponseRenderer:
    if not settings.openai_api_key:
        logger.warning("Cannot build response renderer because OPENAI_API_KEY is missing")
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for chat")
    logger.debug("Building template response renderer")
    return TemplateResponseRenderer()


def get_chat_service(
    conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
    request_intent_classifier: Annotated[
        RequestIntentClassifier,
        Depends(get_request_intent_classifier),
    ],
    intent_extractor: Annotated[IntentExtractor, Depends(get_intent_extractor)],
    response_renderer: Annotated[ResponseRenderer, Depends(get_response_renderer)],
    retrieval: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> ChatService:
    logger.debug("Building chat service")
    return ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=request_intent_classifier,
        intent_extractor=intent_extractor,
        response_renderer=response_renderer,
        retrieval=retrieval,
    )
