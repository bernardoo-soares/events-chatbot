from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    city: str
    date_from: date | None = None
    date_to: date | None = None
    size: int = Field(default=200, gt=0)


class IngestionSummary(BaseModel):
    source: str
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    errors: int = 0


class UpsertSummary(BaseModel):
    inserted: int = 0
    updated: int = 0


class SourcePayload(BaseModel):
    source: str
    source_event_id: str
    payload: dict[str, Any]


class SourceEvent(BaseModel):
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

