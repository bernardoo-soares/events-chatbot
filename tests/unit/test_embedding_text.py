from datetime import UTC, datetime

from event_chatbot.retrieval.embedding_text import (
    build_event_embedding_text,
    build_query_embedding_text,
    embedding_text_hash,
)
from event_chatbot.types.events import Event
from event_chatbot.types.query import HardFilters, NormalizedQuery


def test_build_event_embedding_text_uses_structured_event_fields() -> None:
    now = datetime(2026, 5, 22, tzinfo=UTC)
    event = Event(
        id=1,
        source="agendalx",
        source_event_id="event-1",
        title="Lisbon Wine Tasting",
        description="Portuguese wines with small plates.",
        city="Lisbon",
        venue_name="Mercado",
        category="food_drink",
        subcategory="wine",
        start_at=now,
        ingested_at=now,
        last_seen_at=now,
    )

    text = build_event_embedding_text(event)

    assert "Local event or activity listing" in text
    assert "Title: Lisbon Wine Tasting" in text
    assert "Description: Portuguese wines with small plates." in text
    assert "Category: food_drink" in text
    assert "Subcategory: wine" in text
    assert "Venue: Mercado" in text
    assert "City: Lisbon" in text


def test_build_query_embedding_text_uses_normalized_query_terms() -> None:
    query = NormalizedQuery(
        hard_filters=HardFilters(city="Lisbon", max_price=30),
        fts_terms=["wine"],
        category_boosts=["food_drink"],
        vibe_tags=["relaxed"],
        semantic_terms=["wine", "drinks", "food_drink", "relaxed"],
    )

    text = build_query_embedding_text(query)

    assert "Local event or activity search" in text
    assert "City: Lisbon" in text
    assert "Search terms: wine, drinks, food_drink, relaxed" in text
    assert "Event categories: food_drink" in text
    assert "Vibes: relaxed" in text
    assert "Budget: under 30" in text


def test_embedding_text_hash_is_stable_and_content_sensitive() -> None:
    first = embedding_text_hash("Title: A")
    second = embedding_text_hash("Title: A")
    changed = embedding_text_hash("Title: B")

    assert first == second
    assert first != changed
