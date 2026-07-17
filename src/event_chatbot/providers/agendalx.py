import re
from datetime import datetime, time
from html import unescape
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from event_chatbot.core.logging import get_logger
from event_chatbot.types.ingestion import IngestionRequest, SourceEvent, SourcePayload

LISBON_TIMEZONE = "Europe/Lisbon"
LISBON_CITY = "Lisbon"
logger = get_logger(__name__)


class AgendaLXProviderError(RuntimeError):
    pass


class AgendaLXProvider:
    source = "agendalx"

    def __init__(
        self,
        base_url: str,
        per_page: int = 100,
        client: httpx.Client | None = None,
        max_pages: int = 100,
    ):
        self.base_url = base_url.rstrip("/")
        self.per_page = min(per_page, 100)
        self.max_pages = max_pages
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "EventsChatBot/0.1"},
        )

    def fetch_events(self, request: IngestionRequest) -> list[SourcePayload]:
        logger.info(
            "Fetching AgendaLX events requested_size=%s per_page=%s base_url=%s",
            request.size,
            self.per_page,
            self.base_url,
        )
        payloads: list[SourcePayload] = []
        page = 1

        while len(payloads) < request.size and page <= self.max_pages:
            page_size = min(self.per_page, request.size - len(payloads))
            response = self.client.get(
                f"{self.base_url}/events",
                params={"per_page": page_size, "page": page},
            )
            logger.debug(
                "AgendaLX response received page=%s page_size=%s status=%s",
                page,
                page_size,
                response.status_code,
            )
            if response.status_code >= 400:
                logger.error(
                    "AgendaLX request failed page=%s status=%s body_preview=%s",
                    page,
                    response.status_code,
                    response.text[:300],
                )
                raise AgendaLXProviderError(
                    f"AgendaLX request failed with status {response.status_code}"
                )

            events = response.json()
            if not isinstance(events, list) or not events:
                logger.info("AgendaLX pagination stopped page=%s reason=empty_response", page)
                break

            skipped_past = 0
            for event in events:
                if not isinstance(event, dict) or event.get("id") is None:
                    continue
                if not _is_current_or_future_payload(event):
                    skipped_past += 1
                    continue
                payloads.append(
                    SourcePayload(
                        source=self.source,
                        source_event_id=str(event["id"]),
                        payload=event,
                    )
                )
                if len(payloads) >= request.size:
                    break

            if len(events) < page_size:
                logger.info(
                    "AgendaLX pagination stopped page=%s "
                    "reason=short_page events=%s skipped_past=%s",
                    page,
                    len(events),
                    skipped_past,
                )
                break
            logger.debug(
                "AgendaLX page processed page=%s returned=%s accepted_total=%s skipped_past=%s",
                page,
                len(events),
                len(payloads),
                skipped_past,
            )
            page += 1

        if page > self.max_pages and len(payloads) < request.size:
            logger.warning(
                "AgendaLX pagination hit max_pages=%s before reaching requested size=%s "
                "(collected=%s); stopping to avoid unbounded requests",
                self.max_pages,
                request.size,
                len(payloads),
            )

        logger.info("AgendaLX fetch completed payload_count=%s", len(payloads))
        return payloads


def normalize_agendalx_event(payload: SourcePayload, fetched_at: datetime) -> SourceEvent:
    event = payload.payload
    start_at = _date_to_datetime(event.get("StartDate"), end_of_day=False)
    if start_at is None:
        raise ValueError(f"AgendaLX event {payload.source_event_id} has no StartDate")

    end_at = _date_to_datetime(event.get("LastDate"), end_of_day=True)
    if not _is_current_or_future_dates(start_at, end_at, fetched_at):
        raise ValueError(f"AgendaLX event {payload.source_event_id} ended before today")

    category = _first_taxonomy_name(event.get("categories_name_list")) or _clean_text(
        event.get("subject")
    )
    subcategory = _first_taxonomy_name(event.get("tags_name_list"))

    return SourceEvent(
        source=payload.source,
        source_event_id=payload.source_event_id,
        title=_title(event) or "Untitled event",
        description=_description(event),
        city=LISBON_CITY,
        venue_name=_venue_name(event.get("venue")),
        category=category,
        subcategory=subcategory,
        start_at=start_at,
        end_at=end_at,
        timezone=LISBON_TIMEZONE,
        min_price=None,
        max_price=None,
        currency=None,
        status="scheduled",
        url=_clean_text(event.get("link")),
        image_url=_clean_text(event.get("featured_media_large")),
        latitude=None,
        longitude=None,
    )


def _is_current_or_future_payload(event: dict[str, Any]) -> bool:
    start_at = _date_to_datetime(event.get("StartDate"), end_of_day=False)
    if start_at is None:
        return False
    end_at = _date_to_datetime(event.get("LastDate"), end_of_day=True)
    now = datetime.now(ZoneInfo(LISBON_TIMEZONE))
    return _is_current_or_future_dates(start_at, end_at, now)


def _is_current_or_future_dates(
    start_at: datetime,
    end_at: datetime | None,
    now: datetime,
) -> bool:
    timezone = ZoneInfo(LISBON_TIMEZONE)
    today_start = datetime.combine(
        now.astimezone(timezone).date(),
        time.min,
        tzinfo=timezone,
    )
    if end_at is not None:
        return end_at >= today_start
    return start_at >= today_start


def _date_to_datetime(value: object, *, end_of_day: bool) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed_date = datetime.fromisoformat(value.strip()).date()
    parsed_time = time(23, 59, 59) if end_of_day else time.min
    return datetime.combine(parsed_date, parsed_time, tzinfo=ZoneInfo(LISBON_TIMEZONE))


def _title(event: dict[str, Any]) -> str | None:
    title = event.get("title")
    if isinstance(title, dict):
        return _clean_text(title.get("rendered"))
    return _clean_text(title)


def _description(event: dict[str, Any]) -> str | None:
    value = event.get("description")
    if isinstance(value, list):
        return _clean_text(" ".join(str(item) for item in value))
    return _clean_text(value)


def _venue_name(value: object) -> str | None:
    if isinstance(value, dict):
        first = next(iter(value.values()), None)
        if isinstance(first, dict):
            return _clean_text(first.get("name"))
    return None


def _first_taxonomy_name(value: object) -> str | None:
    if isinstance(value, dict):
        first = next(iter(value.values()), None)
        if isinstance(first, dict):
            return _clean_text(first.get("name"))
    return None


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    cleaned = " ".join(text.split())
    return cleaned or None
