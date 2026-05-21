import sqlite3
from collections.abc import Callable
from datetime import datetime

from event_chatbot.core.logging import get_logger
from event_chatbot.db.connection import transaction
from event_chatbot.providers.event_source import EventSourceProvider
from event_chatbot.repositories.events import EventRepository
from event_chatbot.repositories.raw_events import RawEventRepository
from event_chatbot.types.ingestion import (
    IngestionRequest,
    IngestionSummary,
    SourceEvent,
    SourcePayload,
)

EventNormalizer = Callable[[SourcePayload, datetime], SourceEvent]
Clock = Callable[[], datetime]
logger = get_logger(__name__)


class IngestionService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        provider: EventSourceProvider,
        normalizer: EventNormalizer,
        clock: Clock,
    ):
        self.conn = conn
        self.provider = provider
        self.normalizer = normalizer
        self.clock = clock
        self.raw_events = RawEventRepository(conn)
        self.events = EventRepository(conn)

    def ingest(self, request: IngestionRequest) -> IngestionSummary:
        logger.info(
            "Ingestion started source=%s city=%s size=%s date_from=%s date_to=%s",
            request.source,
            request.city,
            request.size,
            request.date_from,
            request.date_to,
        )
        fetched_at = self.clock()
        payloads = self.provider.fetch_events(request)
        logger.info(
            "Ingestion provider fetched source=%s payload_count=%s",
            self.provider.source,
            len(payloads),
        )
        normalized_events: list[SourceEvent] = []
        errors = 0

        for payload in payloads:
            try:
                normalized_events.append(self.normalizer(payload, fetched_at))
            except (KeyError, TypeError, ValueError):
                errors += 1
                logger.exception(
                    "Failed to normalize event source=%s source_event_id=%s",
                    payload.source,
                    payload.source_event_id,
                )

        with transaction(self.conn):
            self.raw_events.upsert_many(payloads, fetched_at)
            event_summary = self.events.upsert_many(normalized_events, fetched_at)

        summary = IngestionSummary(
            source=self.provider.source,
            fetched=len(payloads),
            inserted=event_summary.inserted,
            updated=event_summary.updated,
            errors=errors,
        )
        logger.info(
            "Ingestion completed source=%s fetched=%s inserted=%s updated=%s errors=%s",
            summary.source,
            summary.fetched,
            summary.inserted,
            summary.updated,
            summary.errors,
        )
        return summary
