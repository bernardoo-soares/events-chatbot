from datetime import UTC, datetime

from event_chatbot.db.connection import connect
from event_chatbot.db.migrations import initialize_database
from event_chatbot.providers.event_source import EventSourceProvider
from event_chatbot.services.ingestion_service import IngestionService
from event_chatbot.types.ingestion import IngestionRequest, SourceEvent, SourcePayload


class FakeProvider(EventSourceProvider):
    def fetch_events(self, request: IngestionRequest) -> list[SourcePayload]:
        return [
            SourcePayload(
                source="fake",
                source_event_id="event-1",
                payload={"title": "Fake Jazz Night"},
            )
        ]


def fake_normalizer(payload: SourcePayload, fetched_at: datetime) -> SourceEvent:
    return SourceEvent(
        source=payload.source,
        source_event_id=payload.source_event_id,
        title=payload.payload["title"],
        city="Lisbon",
        category="music",
        subcategory="jazz",
        start_at=fetched_at,
        status="onsale",
    )


def test_ingestion_service_stores_raw_and_normalized_events(tmp_path) -> None:
    conn = connect(str(tmp_path / "ingestion.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 23, 0, tzinfo=UTC)
    service = IngestionService(
        conn=conn,
        provider=FakeProvider(),
        normalizer=fake_normalizer,
        clock=lambda: now,
    )

    summary = service.ingest(IngestionRequest(city="Lisbon", size=1))

    assert summary.source == "fake"
    assert summary.fetched == 1
    assert summary.inserted == 1
    assert summary.updated == 0
    assert summary.errors == 0
    assert conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1

