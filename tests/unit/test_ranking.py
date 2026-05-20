from datetime import UTC, datetime, timedelta

from event_chatbot.retrieval.ranking import (
    compute_price_score,
    compute_tag_overlap_score,
    compute_temporal_score,
    rank_candidates,
)
from event_chatbot.types.events import EventCandidate
from event_chatbot.types.query import HardFilters, NormalizedQuery


def make_candidate(
    event_id: int,
    start_at: datetime,
    min_price: float | None,
    bm25_score: float | None = None,
    category: str | None = "music",
    subcategory: str | None = "jazz",
) -> EventCandidate:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    return EventCandidate(
        id=event_id,
        source="test",
        source_event_id=f"event-{event_id}",
        title=f"Event {event_id}",
        start_at=start_at,
        min_price=min_price,
        category=category,
        subcategory=subcategory,
        ingested_at=now,
        last_seen_at=now,
        bm25_score=bm25_score,
    )


def test_rank_candidates_converts_bm25_lower_is_better() -> None:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    query = NormalizedQuery(
        hard_filters=HardFilters(date_from=now),
        used_fts=True,
        category_boosts=["music"],
    )
    candidates = [
        make_candidate(1, now + timedelta(hours=1), 20, bm25_score=10),
        make_candidate(2, now + timedelta(hours=1), 20, bm25_score=1),
    ]

    ranked = rank_candidates(candidates, query, now)

    assert ranked[0].event.id == 2
    assert ranked[0].lexical_score == 1.0
    assert ranked[1].lexical_score == 0.0


def test_temporal_price_and_tag_component_rules() -> None:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    query = NormalizedQuery(
        hard_filters=HardFilters(date_from=now, max_price=30),
        category_boosts=["music"],
        vibe_tags=["jazz"],
    )
    matching = make_candidate(1, now, 20)
    unknown_price = make_candidate(2, now, None)
    over_budget = make_candidate(3, now, 45)
    past = make_candidate(4, now - timedelta(hours=1), 20)

    assert compute_temporal_score(matching, query, now) == 1.0
    assert compute_temporal_score(past, query, now) == 0.0
    assert compute_price_score(matching, query) == 1.0
    assert compute_price_score(unknown_price, query) == 0.6
    assert compute_price_score(over_budget, query) == 0.5
    assert compute_tag_overlap_score(matching, query) == 1.0

