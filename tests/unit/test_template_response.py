from datetime import UTC, datetime

from event_chatbot.providers.template_response import EMPTY_RESPONSE, TemplateResponseRenderer
from event_chatbot.types.events import EventCandidate
from event_chatbot.types.query import HardFilters, NormalizedQuery, RankedEvent


def test_template_response_renderer_formats_events_without_raw_iso_dates() -> None:
    renderer = TemplateResponseRenderer()
    query = NormalizedQuery(hard_filters=HardFilters(city="Lisbon"))
    events = [
        RankedEvent(
            event=EventCandidate(
                id=1,
                source="agendalx",
                source_event_id="event-1",
                title="Paulo Canilhas",
                city="Lisbon",
                venue_name="23a Galeria de Arte",
                category="artes",
                start_at=datetime(2026, 5, 23, tzinfo=UTC),
                end_at=datetime(2026, 5, 30, 23, 59, 59, tzinfo=UTC),
                status="scheduled",
                ingested_at=datetime(2026, 5, 20, tzinfo=UTC),
                last_seen_at=datetime(2026, 5, 20, tzinfo=UTC),
            ),
            score=0.8,
            lexical_score=1.0,
            temporal_score=0.8,
            price_score=0.5,
            tag_overlap_score=0.5,
        )
    ]

    result = renderer.render_response(query, events)

    assert "I found 1 event in Lisbon." in result
    assert "1. Paulo Canilhas" in result
    assert "Date: May 23, 2026 - May 30, 2026" in result
    assert "Venue: 23a Galeria de Arte" in result
    assert "T00:00:00" not in result
    assert result.endswith("Hope one of these fits your mood.")


def test_template_response_renderer_handles_empty_results() -> None:
    renderer = TemplateResponseRenderer()

    result = renderer.render_response(NormalizedQuery(hard_filters=HardFilters()), [])

    assert result == EMPTY_RESPONSE
