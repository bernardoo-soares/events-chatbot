from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from event_chatbot.core.logging import get_logger
from event_chatbot.types.ingestion import IngestionRequest, SourceEvent, SourcePayload

logger = get_logger(__name__)


class TicketmasterProviderError(RuntimeError):
    pass


class TicketmasterProvider:
    source = "ticketmaster"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        client: httpx.Client | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=20.0)

    def fetch_events(self, request: IngestionRequest) -> list[SourcePayload]:
        logger.info(
            "Fetching Ticketmaster events city=%s requested_size=%s date_from=%s date_to=%s",
            request.city,
            request.size,
            request.date_from,
            request.date_to,
        )
        payloads: list[SourcePayload] = []
        page = 0
        page_size = min(request.size, 200)

        while len(payloads) < request.size:
            params: dict[str, Any] = {
                "apikey": self.api_key,
                "city": request.city,
                "size": min(page_size, request.size - len(payloads)),
                "page": page,
                "sort": "date,asc",
            }
            if request.date_from is not None:
                params["startDateTime"] = f"{request.date_from.isoformat()}T00:00:00Z"
            if request.date_to is not None:
                params["endDateTime"] = f"{request.date_to.isoformat()}T23:59:59Z"

            response = self.client.get(f"{self.base_url}/events.json", params=params)
            logger.debug(
                "Ticketmaster response received city=%s page=%s size=%s status=%s",
                request.city,
                page,
                params["size"],
                response.status_code,
            )
            if response.status_code >= 400:
                logger.error(
                    "Ticketmaster request failed city=%s page=%s status=%s body_preview=%s",
                    request.city,
                    page,
                    response.status_code,
                    response.text[:300],
                )
                raise TicketmasterProviderError(
                    f"Ticketmaster request failed with status {response.status_code}"
                )
            data = response.json()
            events = data.get("_embedded", {}).get("events", [])
            if not events:
                logger.info(
                    "Ticketmaster pagination stopped city=%s page=%s reason=no_events",
                    request.city,
                    page,
                )
                break

            for event in events:
                source_event_id = event.get("id")
                if not source_event_id:
                    continue
                payloads.append(
                    SourcePayload(
                        source=self.source,
                        source_event_id=source_event_id,
                        payload=event,
                    )
                )
                if len(payloads) >= request.size:
                    break

            page += 1
            total_pages = data.get("page", {}).get("totalPages")
            if total_pages is not None and page >= int(total_pages):
                logger.info(
                    "Ticketmaster pagination stopped city=%s page=%s total_pages=%s",
                    request.city,
                    page,
                    total_pages,
                )
                break

        logger.info(
            "Ticketmaster fetch completed city=%s payload_count=%s",
            request.city,
            len(payloads),
        )
        return payloads


def normalize_ticketmaster_event(payload: SourcePayload, fetched_at: datetime) -> SourceEvent:
    event = payload.payload
    venue = _first(event.get("_embedded", {}).get("venues", []))
    classification = _first(event.get("classifications", []))
    price_range = _first(event.get("priceRanges", []))
    image = _best_image(event.get("images", []))

    start_at = _parse_start_at(event)
    if start_at is None:
        raise ValueError(f"Ticketmaster event {payload.source_event_id} has no start date")

    return SourceEvent(
        source=payload.source,
        source_event_id=payload.source_event_id,
        title=event.get("name") or "Untitled event",
        description=event.get("description") or event.get("info") or event.get("pleaseNote"),
        city=venue.get("city", {}).get("name") if venue else None,
        venue_name=venue.get("name") if venue else None,
        category=_nested_name(classification, "segment"),
        subcategory=_nested_name(classification, "genre"),
        start_at=start_at,
        end_at=None,
        timezone=event.get("dates", {}).get("timezone"),
        min_price=price_range.get("min") if price_range else None,
        max_price=price_range.get("max") if price_range else None,
        currency=price_range.get("currency") if price_range else None,
        status=event.get("dates", {}).get("status", {}).get("code") or "unknown",
        url=event.get("url"),
        image_url=image.get("url") if image else None,
        latitude=_float_or_none(venue.get("location", {}).get("latitude")) if venue else None,
        longitude=_float_or_none(venue.get("location", {}).get("longitude")) if venue else None,
    )


def _parse_start_at(event: dict[str, Any]) -> datetime | None:
    start = event.get("dates", {}).get("start", {})
    date_time = start.get("dateTime")
    if date_time:
        return datetime.fromisoformat(date_time.replace("Z", "+00:00"))

    local_date = start.get("localDate")
    if not local_date:
        return None
    local_time = start.get("localTime")
    timezone_name = event.get("dates", {}).get("timezone") or "UTC"
    parsed_time = time.fromisoformat(local_time) if local_time else time(0, 0)
    parsed_date = datetime.fromisoformat(local_date).date()
    return datetime.combine(parsed_date, parsed_time, tzinfo=ZoneInfo(timezone_name))


def _first(values: list[dict[str, Any]]) -> dict[str, Any] | None:
    return values[0] if values else None


def _nested_name(value: dict[str, Any] | None, key: str) -> str | None:
    if value is None:
        return None
    nested = value.get(key)
    return nested.get("name") if isinstance(nested, dict) else None


def _best_image(images: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not images:
        return None
    return max(images, key=lambda image: image.get("width", 0) * image.get("height", 0))


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
