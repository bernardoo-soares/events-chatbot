import sqlite3
from collections.abc import Callable
from datetime import datetime

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
        fetched_at = self.clock()
        payloads = self.provider.fetch_events(request)
        normalized_events: list[SourceEvent] = []
        errors = 0

        for payload in payloads:
            try:
                normalized_events.append(self.normalizer(payload, fetched_at))
            except (KeyError, TypeError, ValueError):
                errors += 1

        with transaction(self.conn):
            self.raw_events.upsert_many(payloads, fetched_at)
            event_summary = self.events.upsert_many(normalized_events, fetched_at)

        return IngestionSummary(
            source=payloads[0].source if payloads else "ticketmaster",
            fetched=len(payloads),
            inserted=event_summary.inserted,
            updated=event_summary.updated,
            errors=errors,
        )

