from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from event_chatbot.api.dependencies import get_chat_service
from event_chatbot.db.connection import connect
from event_chatbot.db.migrations import initialize_database
from event_chatbot.main import create_app
from event_chatbot.providers.llm import IntentExtractor, RequestIntentClassifier, ResponseRenderer
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.services.chat_service import ChatService
from event_chatbot.types.chat import SessionState
from event_chatbot.types.ingestion import SourceEvent
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent, RequestIntent


class FakeRequestIntentClassifier(RequestIntentClassifier):
    def classify_request_intent(self, message: str, state: SessionState | None) -> RequestIntent:
        return RequestIntent(
            primary_intent="event_search",
            wants_real_world_activity=True,
            wants_catalog_event=True,
            confidence=0.95,
        )


class StaticRequestIntentClassifier(RequestIntentClassifier):
    def __init__(self, request_intent: RequestIntent):
        self.request_intent = request_intent

    def classify_request_intent(self, message: str, state: SessionState | None) -> RequestIntent:
        return self.request_intent


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


class BroadLisbonIntentExtractor(IntentExtractor):
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        return QuerySpec(city="Lisbon")


class ContextAwareIntentExtractor(IntentExtractor):
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        if message == "first":
            return QuerySpec(city="Madrid", keywords=["under 25 euros"], max_price=25)
        if message == "second":
            assert state is None
            return QuerySpec(city="Lisbon", vibes=["relaxed"], date_text="this weekend")
        if message == "tomorrow":
            assert state is not None
            return QuerySpec(date_text="tomorrow")
        raise AssertionError(f"Unexpected message: {message}")


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
        request_intent_classifier=FakeRequestIntentClassifier(),
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


def test_chat_endpoint_caps_results_to_five(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_limit.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    event_repo = EventRepository(conn)
    event_repo.upsert_many(
        [
            SourceEvent(
                source="agendalx",
                source_event_id=f"event-{index}",
                title=f"Lisbon Event {index}",
                city="Lisbon",
                category="arts",
                start_at=now + timedelta(days=index),
                status="scheduled",
            )
            for index in range(1, 9)
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
        request_intent_classifier=FakeRequestIntentClassifier(),
        intent_extractor=BroadLisbonIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=retrieval,
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"session_id": "session-limit", "message": "show me jazz tonight"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 5
    assert body["applied_filters"]["limit"] == 5


def test_chat_endpoint_rejects_obvious_non_event_request(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_scope.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    retrieval = RetrievalService(
        event_repository=EventRepository(conn),
        clock=lambda: now,
        default_timezone="Europe/Lisbon",
        default_days=30,
    )
    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=FakeRequestIntentClassifier(),
        intent_extractor=BroadLisbonIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=retrieval,
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"session_id": "session-weather", "message": "What is the weather today?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "event recommendations" in body["assistant_message"]
    assert body["results"] == []
    assert body["applied_filters"] == {}


def test_chat_endpoint_rejects_llm_classified_non_event_request(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_llm_scope.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=StaticRequestIntentClassifier(
            RequestIntent(
                primary_intent="travel",
                confidence=0.93,
                excluded_reason="The user is asking for hotels.",
            )
        ),
        intent_extractor=BroadLisbonIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=RetrievalService(
            event_repository=EventRepository(conn),
            clock=lambda: now,
            default_timezone="Europe/Lisbon",
            default_days=30,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"session_id": "session-hotels", "message": "Best places to stay in Lisbon"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "event recommendations" in body["assistant_message"]
    assert body["results"] == []
    assert body["applied_filters"] == {}


def test_chat_endpoint_allows_time_bound_food_drink_activity(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_wine.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    event_repo = EventRepository(conn)
    event_repo.upsert_many(
        [
            SourceEvent(
                source="agendalx",
                source_event_id="wine-1",
                title="Lisbon Wine Tasting",
                description="Wine, small plates, and relaxed conversation",
                city="Lisbon",
                category="food_drink",
                subcategory="wine",
                start_at=now + timedelta(hours=6),
                status="scheduled",
            )
        ],
        now,
    )
    conn.commit()

    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=StaticRequestIntentClassifier(
            RequestIntent(
                primary_intent="venue_recommendation",
                is_time_bound=True,
                wants_real_world_activity=True,
                city="Lisbon",
                date_text="today",
                activity_terms=["wine", "drinks"],
                confidence=0.91,
            )
        ),
        intent_extractor=BroadLisbonIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=RetrievalService(
            event_repository=event_repo,
            clock=lambda: now,
            default_timezone="Europe/Lisbon",
            default_days=30,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"session_id": "session-wine", "message": "Give me a place to drink wine today"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assistant_message"] == "Found 1 event: Lisbon Wine Tasting"
    assert body["results"][0]["event"]["title"] == "Lisbon Wine Tasting"
    assert "wine" in body["applied_filters"]["fts_terms"]


def test_chat_endpoint_clarifies_low_confidence_scope(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_low_confidence.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=StaticRequestIntentClassifier(
            RequestIntent(
                primary_intent="unknown",
                confidence=0.52,
                excluded_reason="The request may be event-related but is ambiguous.",
            )
        ),
        intent_extractor=BroadLisbonIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=RetrievalService(
            event_repository=EventRepository(conn),
            clock=lambda: now,
            default_timezone="Europe/Lisbon",
            default_days=30,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"session_id": "session-ambiguous", "message": "Any ideas?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "What kind of plan" in body["assistant_message"]
    assert body["results"] == []
    assert body["applied_filters"] == {}


def test_chat_endpoint_rejects_city_only_query_spec_without_event_language(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_empty_spec.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=FakeRequestIntentClassifier(),
        intent_extractor=BroadLisbonIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=RetrievalService(
            event_repository=EventRepository(conn),
            clock=lambda: now,
            default_timezone="Europe/Lisbon",
            default_days=30,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"session_id": "session-city-only", "message": "Lisbon"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "What kind of plan" in body["assistant_message"]
    assert body["results"] == []
    assert body["applied_filters"] == {}


def test_chat_endpoint_new_search_does_not_carry_stale_previous_filters(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_context_reset.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    event_repo = EventRepository(conn)
    event_repo.upsert_many(
        [
            SourceEvent(
                source="ticketmaster",
                source_event_id="madrid-1",
                title="Madrid Budget Plan",
                city="Madrid",
                start_at=now + timedelta(days=1),
                status="onsale",
            ),
            SourceEvent(
                source="agendalx",
                source_event_id="lisbon-1",
                title="Relaxed Lisbon Weekend",
                city="Lisbon",
                start_at=now + timedelta(days=4),
                status="scheduled",
            ),
        ],
        now,
    )
    conn.commit()
    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=StaticRequestIntentClassifier(
            RequestIntent(
                primary_intent="activity_plan",
                conversation_role="new_search",
                confidence=0.95,
            )
        ),
        intent_extractor=ContextAwareIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=RetrievalService(
            event_repository=event_repo,
            clock=lambda: now,
            default_timezone="Europe/Lisbon",
            default_days=30,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    first = client.post("/chat", json={"session_id": "session-reset", "message": "first"})
    second = client.post("/chat", json={"session_id": "session-reset", "message": "second"})

    assert first.status_code == 200
    assert second.status_code == 200
    body = second.json()
    assert body["applied_filters"]["hard_filters"]["city"] == "Lisbon"
    assert body["applied_filters"]["hard_filters"]["max_price"] is None
    assert "under 25 euros" not in body["applied_filters"]["fts_terms"]
    state = ChatSessionRepository(conn).get_or_create("session-reset", now)
    assert state.current_query is not None
    assert state.current_query.city == "Lisbon"
    assert state.current_query.max_price is None
    assert state.current_query.keywords == []


def test_chat_endpoint_follow_up_carries_declared_previous_fields(tmp_path) -> None:
    conn = connect(str(tmp_path / "chat_context_followup.sqlite"))
    initialize_database(conn)
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    event_repo = EventRepository(conn)
    event_repo.upsert_many(
        [
            SourceEvent(
                source="ticketmaster",
                source_event_id="madrid-comedy",
                title="Madrid Comedy Tomorrow",
                city="Madrid",
                category="comedy",
                start_at=now + timedelta(days=1),
                status="onsale",
            )
        ],
        now,
    )
    conn.commit()
    intents = [
        RequestIntent(
            primary_intent="activity_plan",
            conversation_role="new_search",
            confidence=0.95,
        ),
        RequestIntent(
            primary_intent="activity_plan",
            conversation_role="follow_up_refinement",
            context_carryover=["city", "budget", "keywords"],
            confidence=0.95,
        ),
    ]

    class SequenceRequestIntentClassifier(RequestIntentClassifier):
        def classify_request_intent(
            self,
            message: str,
            state: SessionState | None,
        ) -> RequestIntent:
            return intents.pop(0)

    service = ChatService(
        conn=conn,
        sessions=ChatSessionRepository(conn),
        request_intent_classifier=SequenceRequestIntentClassifier(),
        intent_extractor=ContextAwareIntentExtractor(),
        response_renderer=FakeResponseRenderer(),
        retrieval=RetrievalService(
            event_repository=event_repo,
            clock=lambda: now,
            default_timezone="Europe/Lisbon",
            default_days=30,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    client = TestClient(app)

    first = client.post("/chat", json={"session_id": "session-followup", "message": "first"})
    second = client.post("/chat", json={"session_id": "session-followup", "message": "tomorrow"})

    assert first.status_code == 200
    assert second.status_code == 200
    body = second.json()
    assert body["applied_filters"]["hard_filters"]["city"] == "Madrid"
    assert body["applied_filters"]["hard_filters"]["max_price"] == 25
    assert "under 25 euros" in body["applied_filters"]["fts_terms"]
