from datetime import UTC, datetime

from event_chatbot.retrieval.normalization import normalize_query
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import QuerySpec


def test_normalize_query_turns_tonight_into_evening_window_and_soft_signals() -> None:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    spec = QuerySpec(
        city=" Lisbon ",
        raw_category_text="chill gig with drinks",
        categories=["music", "concerts"],
        keywords=["jazz"],
        vibes=["chill"],
        date_text="tonight",
        max_price=30,
    )

    query = normalize_query(
        spec,
        previous=None,
        now=now,
        default_timezone="Europe/Lisbon",
        default_days=30,
    )

    assert query.hard_filters.city == "Lisbon"
    assert query.city_slug == "lisbon"
    assert query.hard_filters.date_from is not None
    assert query.hard_filters.date_from.hour == 18
    assert query.hard_filters.date_to is not None
    assert query.hard_filters.date_to.hour == 23
    assert query.hard_filters.max_price == 30
    assert query.category_boosts == ["music"]
    assert query.hard_filters.hard_category_filters == []
    assert "concerts" not in query.fts_terms
    assert "chill" in query.vibe_tags
    assert query.used_fts is True


def test_hard_category_only_moves_category_to_hard_filter() -> None:
    query = normalize_query(
        QuerySpec(categories=["sports"], hard_category_only=True),
        previous=None,
        now=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        default_timezone="Europe/Lisbon",
        default_days=30,
    )

    assert query.category_boosts == ["sports"]
    assert query.hard_filters.hard_category_filters == ["sports"]


def test_default_status_filter_includes_scheduled_events() -> None:
    query = normalize_query(
        QuerySpec(city="Lisbon"),
        previous=None,
        now=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        default_timezone="Europe/Lisbon",
        default_days=30,
    )

    assert query.hard_filters.statuses == ["onsale", "scheduled", "unknown"]


def test_category_aliases_are_soft_boosts_not_fts_requirements() -> None:
    query = normalize_query(
        QuerySpec(categories=["art", "theater", "food", "festival"]),
        previous=None,
        now=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        default_timezone="Europe/Lisbon",
        default_days=30,
    )

    assert query.category_boosts == ["arts", "theatre", "food_drink"]
    assert query.hard_filters.hard_category_filters == []
    assert "festival" not in query.fts_terms


def test_past_only_date_window_falls_back_to_default_upcoming_window() -> None:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)

    query = normalize_query(
        QuerySpec(date_from="2023-10-01", date_to="2023-10-31"),
        previous=None,
        now=now,
        default_timezone="Europe/Lisbon",
        default_days=30,
    )

    assert query.hard_filters.date_from == now
    assert query.hard_filters.date_to == datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def test_normalize_query_does_not_merge_previous_without_carryover_fields() -> None:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    previous = SessionState(
        session_id="session-1",
        created_at=now,
        updated_at=now,
        current_query=QuerySpec(
            city="Madrid",
            keywords=["under 25 euros"],
            max_price=25,
        ),
    )

    query = normalize_query(
        QuerySpec(city="Lisbon", vibes=["relaxed"], date_text="this weekend"),
        previous=previous,
        carryover_fields=set(),
        now=now,
        default_timezone="Europe/Lisbon",
        default_days=30,
    )

    assert query.hard_filters.city == "Lisbon"
    assert query.hard_filters.max_price is None
    assert "under 25 euros" not in query.fts_terms


def test_normalize_query_merges_only_allowed_previous_fields() -> None:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    previous = SessionState(
        session_id="session-1",
        created_at=now,
        updated_at=now,
        current_query=QuerySpec(
            city="Madrid",
            keywords=["comedy"],
            max_price=25,
            date_text="tonight",
        ),
    )

    query = normalize_query(
        QuerySpec(date_text="tomorrow"),
        previous=previous,
        carryover_fields={"city", "budget", "keywords"},
        now=now,
        default_timezone="Europe/Lisbon",
        default_days=30,
    )

    assert query.hard_filters.city == "Madrid"
    assert query.hard_filters.max_price == 25
    assert "comedy" in query.fts_terms
    assert query.hard_filters.date_from is not None
    assert query.hard_filters.date_from.date().isoformat() == "2026-05-20"
