from datetime import UTC, datetime, timedelta

from event_chatbot.db.connection import connect, transaction
from event_chatbot.db.migrations import initialize_database
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.types.ingestion import SourceEvent
from event_chatbot.types.query import QuerySpec


def test_retrieval_service_normalizes_searches_and_ranks(tmp_path) -> None:
    conn = connect(str(tmp_path / "retrieval.sqlite"))
    initialize_database(conn)
    repo = EventRepository(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    service = RetrievalService(
        event_repository=repo,
        clock=lambda: now,
        default_timezone="Europe/Lisbon",
        default_days=30,
    )
    with transaction(conn):
        repo.upsert_many(
            [
                SourceEvent(
                    source="ticketmaster",
                    source_event_id="event-1",
                    title="Lisbon Jazz Night",
                    description="Live jazz and cocktails",
                    city="Lisbon",
                    category="music",
                    subcategory="jazz",
                    start_at=now + timedelta(hours=8),
                    min_price=20,
                    status="onsale",
                ),
                SourceEvent(
                    source="ticketmaster",
                    source_event_id="event-2",
                    title="Lisbon Football Match",
                    city="Lisbon",
                    category="sports",
                    subcategory="football",
                    start_at=now + timedelta(hours=8),
                    min_price=20,
                    status="onsale",
                ),
            ],
            now,
        )

    query = service.normalize(
        QuerySpec(
            city="Lisbon",
            keywords=["jazz"],
            date_text="tonight",
            max_price=30,
        )
    )
    results = service.search(query)

    assert results
    assert results[0].event.title == "Lisbon Jazz Night"

