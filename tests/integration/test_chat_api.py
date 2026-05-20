from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from event_chatbot.api.dependencies import get_chat_service
from event_chatbot.db.connection import connect
from event_chatbot.db.migrations import initialize_database
from event_chatbot.main import create_app
from event_chatbot.providers.llm import IntentExtractor, ResponseRenderer
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.services.chat_service import ChatService
from event_chatbot.types.chat import SessionState
from event_chatbot.types.ingestion import SourceEvent
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent


class FakeIntentExtractor(IntentExtractor):
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        if "tomorrow" in message:
            return QuerySpec(city="Lisbon", keywords=["jazz"], date_text="tomorrow")
        return QuerySpec(city="Lisbon", keywords=["jazz"], date_text="tonight", max_price=30)


class FakeResponseRenderer(ResponseRenderer):
    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        if not events:
            return "No matching events were found."
        return f"Found {len(events)} event: {events[0].event.title}"


def test_chat_endpoint_returns_grounded_results_and_persists_state(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_api.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    event_repo = EventRepository(conn)
    event_repo.upsert_many(
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
            )
        ],
        now,
    )
    conn.commit()

    retrieval = RetrievalService(
        event_repository=event_repo,
        clock=lambda: now,
        default_timezone="Europe/Lisbon",
        default_days=30,
    )
    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        intent_extractor=FakeIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=retrieval,
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"session_id": "session-1", "message": "show me jazz tonight"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assistant_message"] == "Found 1 event: Lisbon Jazz Night"
    assert body["results"][0]["event"]["title"] == "Lisbon Jazz Night"

    state = ChatSessionRepository(conn).get_or_create("session-1", now)
    assert state.current_query is not None
    assert state.current_query.city == "Lisbon"
    assert state.last_result_ids == [1]
    assert conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0] == 2

