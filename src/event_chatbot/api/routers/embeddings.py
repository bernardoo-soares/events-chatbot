import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from event_chatbot.api.dependencies import SettingsDep, get_db_connection
from event_chatbot.core.time import utc_now
from event_chatbot.providers.embeddings import OpenAIEmbeddingProvider
from event_chatbot.repositories.event_embeddings import EventEmbeddingRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.services.embedding_service import EmbeddingService
from event_chatbot.types.embeddings import EmbeddingBackfillSummary

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


class EmbeddingBackfillRequest(BaseModel):
    limit: int = Field(default=500, gt=0, le=5000)


@router.post("/backfill", response_model=EmbeddingBackfillSummary)
def backfill_embeddings(
    request: EmbeddingBackfillRequest,
    settings: SettingsDep,
    conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
) -> EmbeddingBackfillSummary:
    if not settings.openai_api_key:
        return EmbeddingBackfillSummary(
            model=settings.openai_embedding_model,
            errors=request.limit,
        )

    service = EmbeddingService(
        conn=conn,
        event_repository=EventRepository(conn),
        embedding_repository=EventEmbeddingRepository(conn),
        embedding_provider=OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            batch_size=settings.embedding_batch_size,
        ),
        clock=utc_now,
    )
    return service.backfill_events(request.limit)
