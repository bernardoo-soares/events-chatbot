from datetime import UTC, datetime

from event_chatbot.retrieval.query_builder import build_candidate_query
from event_chatbot.types.query import HardFilters, NormalizedQuery


def test_build_candidate_query_uses_hard_filters_and_fts() -> None:
    query = NormalizedQuery(
        hard_filters=HardFilters(
            city="Lisbon",
            date_from=datetime(2026, 5, 19, tzinfo=UTC),
            date_to=datetime(2026, 5, 20, tzinfo=UTC),
            max_price=30,
            statuses=["onsale"],
            hard_category_filters=["sports"],
        ),
        used_fts=True,
        fts_query="jazz",
        candidate_limit=50,
    )

    sql, params = build_candidate_query(query)

    assert "JOIN events_fts" in sql
    assert "events_fts MATCH ?" in sql
    assert "e.city = ?" in sql
    assert "COALESCE(e.end_at, e.start_at) >= ?" in sql
    assert params[-2:] == ["jazz", 50]
