from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from event_chatbot.providers.agendalx import (
    AgendaLXProvider,
    AgendaLXProviderError,
    normalize_agendalx_event,
)
from event_chatbot.types.ingestion import IngestionRequest, SourcePayload

# Dates are computed relative to "today" so the provider's current/future filter
# accepts (or rejects) them deterministically regardless of when the suite runs.
_FUTURE_START = (date.today() + timedelta(days=30)).isoformat()
_FUTURE_END = (date.today() + timedelta(days=60)).isoformat()
_PAST_START = (date.today() - timedelta(days=400)).isoformat()
_PAST_END = (date.today() - timedelta(days=390)).isoformat()


def test_agendalx_provider_paginates_and_respects_request_size() -> None:
    seen_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        per_page = int(request.url.params["per_page"])
        seen_pages.append(page)
        events = [_agendalx_payload(event_id=page * 1000 + index) for index in range(per_page)]
        return httpx.Response(200, json=events)

    provider = AgendaLXProvider(
        base_url="https://example.test",
        per_page=100,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    payloads = provider.fetch_events(IngestionRequest(source="agendalx", city="Lisbon", size=150))

    assert len(payloads) == 150
    assert seen_pages == [1, 2]
    assert payloads[0].source == "agendalx"


def test_agendalx_provider_stops_on_short_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_agendalx_payload(event_id=1)])

    provider = AgendaLXProvider(
        base_url="https://example.test",
        per_page=100,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    payloads = provider.fetch_events(IngestionRequest(source="agendalx", city="Lisbon", size=100))

    assert len(payloads) == 1


def test_agendalx_provider_skips_past_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _agendalx_payload(event_id=1, start_date=_PAST_START, last_date=_PAST_END),
                _agendalx_payload(event_id=2, start_date=_FUTURE_START, last_date=_FUTURE_END),
            ],
        )

    provider = AgendaLXProvider(
        base_url="https://example.test",
        per_page=100,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    payloads = provider.fetch_events(IngestionRequest(source="agendalx", city="Lisbon", size=100))

    assert [payload.source_event_id for payload in payloads] == ["2"]


def test_agendalx_provider_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    provider = AgendaLXProvider(
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AgendaLXProviderError):
        provider.fetch_events(IngestionRequest(source="agendalx", city="Lisbon", size=1))


def test_normalize_agendalx_event_extracts_schema_fields() -> None:
    payload = SourcePayload(
        source="agendalx",
        source_event_id="123",
        payload=_agendalx_payload(event_id=123, start_date="2026-06-01", last_date="2026-06-30"),
    )

    event = normalize_agendalx_event(payload, datetime(2026, 5, 20, 12, 0, tzinfo=UTC))

    assert event.source == "agendalx"
    assert event.source_event_id == "123"
    assert event.title == "Lisbon Exhibition"
    assert event.description == "A cultural event."
    assert event.city == "Lisbon"
    assert event.venue_name == "Museu de Lisboa"
    assert event.category == "exposicoes"
    assert event.subcategory == "arte"
    assert event.start_at.isoformat() == "2026-06-01T00:00:00+01:00"
    assert event.end_at is not None
    assert event.end_at.isoformat() == "2026-06-30T23:59:59+01:00"
    assert event.timezone == "Europe/Lisbon"
    assert event.status == "scheduled"
    assert event.url == "https://www.agendalx.pt/event/lisbon-exhibition/"
    assert event.image_url == "https://www.agendalx.pt/image.jpg"


def _agendalx_payload(
    *,
    event_id: int,
    start_date: str = _FUTURE_START,
    last_date: str = _FUTURE_END,
) -> dict:
    return {
        "id": event_id,
        "title": {"rendered": "Lisbon Exhibition"},
        "featured_media_large": "https://www.agendalx.pt/image.jpg",
        "subject": "artes",
        "description": ["<p>A cultural event.</p>"],
        "venue": {"456": {"name": "Museu de Lisboa"}},
        "categories_name_list": {"10": {"name": "exposicoes"}},
        "tags_name_list": {"20": {"name": "arte"}},
        "link": "https://www.agendalx.pt/event/lisbon-exhibition/",
        "StartDate": start_date,
        "LastDate": last_date,
    }
