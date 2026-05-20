from datetime import UTC, datetime

from event_chatbot.providers.ticketmaster import normalize_ticketmaster_event
from event_chatbot.types.ingestion import SourcePayload


def test_normalize_ticketmaster_event_extracts_required_fields() -> None:
    payload = SourcePayload(
        source="ticketmaster",
        source_event_id="abc123",
        payload={
            "id": "abc123",
            "name": "Lisbon Jazz Night",
            "description": "Live jazz show",
            "url": "https://example.com/event",
            "dates": {
                "timezone": "Europe/Lisbon",
                "start": {"dateTime": "2026-05-20T20:00:00Z"},
                "status": {"code": "onsale"},
            },
            "classifications": [
                {
                    "segment": {"name": "Music"},
                    "genre": {"name": "Jazz"},
                }
            ],
            "priceRanges": [{"min": 15.0, "max": 30.0, "currency": "EUR"}],
            "images": [
                {"url": "small.jpg", "width": 100, "height": 100},
                {"url": "large.jpg", "width": 400, "height": 300},
            ],
            "_embedded": {
                "venues": [
                    {
                        "name": "Blue Note Lisboa",
                        "city": {"name": "Lisbon"},
                        "location": {"latitude": "38.7223", "longitude": "-9.1393"},
                    }
                ]
            },
        },
    )

    event = normalize_ticketmaster_event(payload, datetime(2026, 5, 19, tzinfo=UTC))

    assert event.source == "ticketmaster"
    assert event.source_event_id == "abc123"
    assert event.title == "Lisbon Jazz Night"
    assert event.city == "Lisbon"
    assert event.venue_name == "Blue Note Lisboa"
    assert event.category == "Music"
    assert event.subcategory == "Jazz"
    assert event.start_at == datetime(2026, 5, 20, 20, 0, tzinfo=UTC)
    assert event.min_price == 15.0
    assert event.max_price == 30.0
    assert event.currency == "EUR"
    assert event.status == "onsale"
    assert event.image_url == "large.jpg"
    assert event.latitude == 38.7223
    assert event.longitude == -9.1393

