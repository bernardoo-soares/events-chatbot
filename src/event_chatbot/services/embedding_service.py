import sqlite3
from collections.abc import Callable
from datetime import datetime

from event_chatbot.core.logging import get_logger
from event_chatbot.db.connection import transaction
from event_chatbot.providers.embeddings import EmbeddingProvider, EmbeddingProviderError
from event_chatbot.repositories.event_embeddings import EventEmbeddingRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.embedding_text import (
    build_event_embedding_text,
    embedding_text_hash,
)
from event_chatbot.types.embeddings import EmbeddingBackfillSummary, EventEmbeddingUpsert

Clock = Callable[[], datetime]
logger = get_logger(__name__)


class EmbeddingService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        event_repository: EventRepository,
        embedding_repository: EventEmbeddingRepository,
        embedding_provider: EmbeddingProvider,
        clock: Clock,
    ):
        self.conn = conn
        self.event_repository = event_repository
        self.embedding_repository = embedding_repository
        self.embedding_provider = embedding_provider
        self.clock = clock

    def backfill_events(self, limit: int) -> EmbeddingBackfillSummary:
        events = self.event_repository.list_for_embedding_backfill(limit)
        summary = EmbeddingBackfillSummary(model=self.embedding_provider.model, checked=len(events))
        if not events:
            return summary

        existing = self.embedding_repository.get_metadata_by_event_ids(
            [event.id for event in events]
        )
        pending: list[tuple[int, str, str]] = []
        for event in events:
            text = build_event_embedding_text(event)
            text_hash = embedding_text_hash(text)
            current = existing.get(event.id)
            if (
                current is not None
                and current.model == self.embedding_provider.model
                and current.embedded_text_hash == text_hash
            ):
                summary.skipped += 1
                continue
            pending.append((event.id, text, text_hash))

        if not pending:
            return summary

        try:
            vectors = self.embedding_provider.embed_texts([item[1] for item in pending])
        except EmbeddingProviderError:
            logger.exception("Embedding backfill failed during provider call")
            summary.errors = len(pending)
            return summary

        upserts = [
            EventEmbeddingUpsert(
                event_id=event_id,
                model=self.embedding_provider.model,
                embedding=vector,
                embedded_text_hash=text_hash,
            )
            for (event_id, _text, text_hash), vector in zip(pending, vectors, strict=True)
        ]

        with transaction(self.conn):
            self.embedding_repository.upsert_many(upserts, self.clock())

        summary.embedded = len(upserts)
        return summary
