from datetime import UTC, datetime, timedelta

from event_chatbot.db.connection import connect, transaction
from event_chatbot.db.migrations import initialize_database
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.repositories.raw_events import RawEventRepository
from event_chatbot.types.ingestion import SourceEvent, SourcePayload
from event_chatbot.types.query import HardFilters, NormalizedQuery, QuerySpec


def test_event_upsert_preserves_id_and_updates_fields(tmp_path) -> None:
    conn = connect(str(tmp_path / "events.sqlite"))
    initialize_database(conn)
    repo = EventRepository(conn)
    now = datetime(2026, 5, 19, 23, 0, tzinfo=UTC)

    event = SourceEvent(
        source="ticketmaster",
        source_event_id="event-1",
        title="Lisbon Jazz Night",
        description="Live jazz",
        city="Lisbon",
        venue_name="Blue Note Lisboa",
        category="music",
        subcategory="jazz",
        start_at=now + timedelta(days=1),
        status="onsale",
    )

    with transaction(conn):
        first = repo.upsert_many([event], now)
    first_id = conn.execute("SELECT id FROM events").fetchone()["id"]

    updated = event.model_copy(update={"title": "Lisbon Rock Night", "subcategory": "rock"})
    with transaction(conn):
        second = repo.upsert_many([updated], now + timedelta(hours=1))
    row = conn.execute("SELECT id, title, subcategory FROM events").fetchone()

    assert first.inserted == 1
    assert first.updated == 0
    assert second.inserted == 0
    assert second.updated == 1
    assert row["id"] == first_id
    assert row["title"] == "Lisbon Rock Night"
    assert row["subcategory"] == "rock"


def test_raw_event_upsert_stores_compact_payload_and_updates(tmp_path) -> None:
    conn = connect(str(tmp_path / "raw.sqlite"))
    initialize_database(conn)
    repo = RawEventRepository(conn)
    now = datetime(2026, 5, 19, 23, 0, tzinfo=UTC)
    payload = SourcePayload(
        source="ticketmaster",
        source_event_id="event-1",
        payload={"name": "Original"},
    )

    with transaction(conn):
        first = repo.upsert_many([payload], now)
        second = repo.upsert_many(
            [payload.model_copy(update={"payload": {"name": "Updated"}})],
            now + timedelta(hours=1),
        )

    rows = conn.execute("SELECT payload_json FROM raw_events").fetchall()
    assert first.inserted == 1
    assert second.updated == 1
    assert len(rows) == 1
    assert rows[0]["payload_json"] == '{"name":"Updated"}'


def test_chat_session_state_and_messages_round_trip(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat.sqlite"))
    initialize_database(conn)
    repo = ChatSessionRepository(conn)
    now = datetime(2026, 5, 19, 23, 0, tzinfo=UTC)

    with transaction(conn):
        state = repo.get_or_create("session-1", now)
        state.current_query = QuerySpec(city="Lisbon", keywords=["jazz"])
        state.last_result_ids = [1, 2, 3]
        repo.save_state("session-1", state, now + timedelta(minutes=1))
        repo.append_message("session-1", "user", "show me jazz", now)

    loaded = repo.get_or_create("session-1", now + timedelta(minutes=2))
    message_count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]

    assert loaded.current_query is not None
    assert loaded.current_query.city == "Lisbon"
    assert loaded.current_query.keywords == ["jazz"]
    assert loaded.last_result_ids == [1, 2, 3]
    assert message_count == 1


def test_event_search_candidates_uses_hard_filters_and_returns_candidate_rows(tmp_path) -> None:
    conn = connect(str(tmp_path / "search.sqlite"))
    initialize_database(conn)
    repo = EventRepository(conn)
    now = datetime(2026, 5, 19, 23, 0, tzinfo=UTC)

    events = [
        SourceEvent(
            source="ticketmaster",
            source_event_id="event-1",
            title="Lisbon Jazz Night",
            city="Lisbon",
            category="music",
            subcategory="jazz",
            start_at=now + timedelta(days=1),
            min_price=20,
            status="onsale",
        ),
        SourceEvent(
            source="ticketmaster",
            source_event_id="event-2",
            title="Porto Jazz Night",
            city="Porto",
            category="music",
            subcategory="jazz",
            start_at=now + timedelta(days=1),
            min_price=20,
            status="onsale",
        ),
    ]
    with transaction(conn):
        repo.upsert_many(events, now)

    query = NormalizedQuery(
        hard_filters=HardFilters(
            city="Lisbon",
            date_from=now,
            date_to=now + timedelta(days=2),
            max_price=30,
            statuses=["onsale"],
        ),
        used_fts=True,
        fts_query="jazz",
        candidate_limit=10,
    )
    candidates = repo.search_candidates(query)

    assert len(candidates) == 1
    assert candidates[0].title == "Lisbon Jazz Night"
    assert candidates[0].bm25_score is not None

