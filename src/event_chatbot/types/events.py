from datetime import datetime

from pydantic import BaseModel


class Event(BaseModel):
    id: int
    source: str
    source_event_id: str
    title: str
    description: str | None = None
    city: str | None = None
    venue_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    timezone: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    currency: str | None = None
    status: str = "unknown"
    url: str | None = None
    image_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    ingested_at: datetime
    last_seen_at: datetime


class EventCandidate(Event):
    bm25_score: float | None = None


class EventUpsert(BaseModel):
    source: str
    source_event_id: str
    title: str
    description: str | None = None
    city: str | None = None
    venue_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    timezone: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    currency: str | None = None
    status: str = "unknown"
    url: str | None = None
    image_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class RawEventUpsert(BaseModel):
    source: str
    source_event_id: str
    payload_json: str
    fetched_at: datetime

