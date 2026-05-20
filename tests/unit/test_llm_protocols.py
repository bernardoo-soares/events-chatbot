from datetime import UTC, datetime

from event_chatbot.providers.llm import IntentExtractor, ResponseRenderer
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import HardFilters, NormalizedQuery, QuerySpec, RankedEvent


class FakeIntentExtractor:
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        return QuerySpec(city="Lisbon", keywords=[message])


class FakeResponseRenderer:
    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        return f"Rendered {len(events)} events"


def test_fake_intent_extractor_satisfies_protocol() -> None:
    extractor: IntentExtractor = FakeIntentExtractor()

    result = extractor.extract_intent("jazz", None)

    assert result.city == "Lisbon"
    assert result.keywords == ["jazz"]


def test_fake_response_renderer_satisfies_protocol() -> None:
    renderer: ResponseRenderer = FakeResponseRenderer()
    query = NormalizedQuery(hard_filters=HardFilters())

    result = renderer.render_response(query, [])

    assert result == "Rendered 0 events"


def test_session_state_can_hold_current_query_for_intent_context() -> None:
    now = datetime(2026, 5, 19, tzinfo=UTC)
    state = SessionState(
        session_id="session-1",
        created_at=now,
        updated_at=now,
        current_query=QuerySpec(city="Lisbon"),
    )

    assert state.current_query is not None
    assert state.current_query.city == "Lisbon"

