from datetime import UTC, datetime

from event_chatbot.retrieval.normalization import normalize_query
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
    assert "concerts" in query.fts_terms
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

