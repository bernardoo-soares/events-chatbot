from datetime import UTC, datetime

from event_chatbot.retrieval.context import (
    allowed_carryover_fields,
    merge_query_spec_for_context,
    should_use_previous_context,
)
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import QuerySpec, RequestIntent


def make_state(query: QuerySpec) -> SessionState:
    now = datetime(2026, 5, 22, tzinfo=UTC)
    return SessionState(
        session_id="session-1",
        created_at=now,
        updated_at=now,
        current_query=query,
    )


def test_new_search_does_not_use_previous_context() -> None:
    intent = RequestIntent(
        primary_intent="activity_plan",
        conversation_role="new_search",
        confidence=0.95,
    )
    state = make_state(QuerySpec(city="Madrid", max_price=25))

    assert should_use_previous_context(intent, state) is False
    assert allowed_carryover_fields(intent) == set()


def test_follow_up_uses_only_declared_carryover_fields() -> None:
    intent = RequestIntent(
        primary_intent="activity_plan",
        conversation_role="follow_up_refinement",
        context_carryover=["city", "budget"],
        confidence=0.95,
    )
    state = make_state(QuerySpec(city="Madrid", max_price=25))

    assert should_use_previous_context(intent, state) is True
    assert allowed_carryover_fields(intent) == {"city", "budget"}


def test_merge_query_spec_for_context_drops_excluded_fields() -> None:
    previous = make_state(
        QuerySpec(
            city="Madrid",
            keywords=["comedy"],
            vibes=["funny"],
            max_price=25,
            date_text="tonight",
        )
    )
    spec = QuerySpec(date_text="tomorrow")

    merged = merge_query_spec_for_context(spec, previous, {"city", "budget"})

    assert merged.city == "Madrid"
    assert merged.date_text == "tomorrow"
    assert merged.max_price == 25
    assert merged.keywords == []
    assert merged.vibes == []
