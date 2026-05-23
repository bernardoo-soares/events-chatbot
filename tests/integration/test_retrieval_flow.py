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
            city="Lisboa",
            keywords=["jazz"],
            date_text="tonight",
            max_price=30,
        )
    )
    results = service.search(query)

    assert results
    assert results[0].event.title == "Lisbon Jazz Night"


def test_retrieval_service_dedupes_repeated_event_titles_before_limit(tmp_path) -> None:
    conn = connect(str(tmp_path / "retrieval_dedupe.sqlite"))
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
                    source_event_id="comedy-1",
                    title="La Otra Movida Comedy",
                    city="Madrid",
                    venue_name="La Otra Movida",
                    category="comedy",
                    start_at=now + timedelta(hours=2),
                    status="onsale",
                ),
                SourceEvent(
                    source="ticketmaster",
                    source_event_id="comedy-2",
                    title="La Otra Movida Comedy",
                    city="Madrid",
                    venue_name="La Otra Movida",
                    category="comedy",
                    start_at=now + timedelta(hours=5),
                    status="onsale",
                ),
                SourceEvent(
                    source="ticketmaster",
                    source_event_id="comedy-3",
                    title="La Otra Movida Comedy",
                    city="Madrid",
                    venue_name="La Otra Movida",
                    category="comedy",
                    start_at=now + timedelta(days=1),
                    status="onsale",
                ),
                SourceEvent(
                    source="ticketmaster",
                    source_event_id="standup-1",
                    title="Madrid Stand-Up Night",
                    city="Madrid",
                    venue_name="Comedy Club Madrid",
                    category="comedy",
                    start_at=now + timedelta(hours=3),
                    status="onsale",
                ),
            ],
            now,
        )

    query = service.normalize(QuerySpec(city="Madrid", keywords=["comedy"]))
    query.limit = 5
    results = service.search(query)

    titles = [result.event.title for result in results]
    assert len(titles) == len(set(titles))
    assert set(titles) == {"La Otra Movida Comedy", "Madrid Stand-Up Night"}


def test_retrieval_service_includes_ongoing_events_but_excludes_fully_past_events(tmp_path) -> None:
    conn = connect(str(tmp_path / "retrieval_ongoing.sqlite"))
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
                    source="agendalx",
                    source_event_id="ongoing-1",
                    title="Ongoing Lisbon Exhibition",
                    city="Lisbon",
                    category="arts",
                    start_at=now - timedelta(days=2),
                    end_at=now + timedelta(days=2),
                    status="scheduled",
                ),
                SourceEvent(
                    source="agendalx",
                    source_event_id="past-1",
                    title="Past Lisbon Exhibition",
                    city="Lisbon",
                    category="arts",
                    start_at=now - timedelta(days=5),
                    end_at=now - timedelta(days=1),
                    status="scheduled",
                ),
                SourceEvent(
                    source="agendalx",
                    source_event_id="future-1",
                    title="Future Lisbon Exhibition",
                    city="Lisbon",
                    category="arts",
                    start_at=now + timedelta(days=1),
                    status="scheduled",
                ),
            ],
            now,
        )

    query = service.normalize(QuerySpec(city="Lisbon", keywords=["exhibition"]))
    query.limit = 10
    results = service.search(query)

    titles = {result.event.title for result in results}
    assert "Ongoing Lisbon Exhibition" in titles
    assert "Future Lisbon Exhibition" in titles
    assert "Past Lisbon Exhibition" not in titles
