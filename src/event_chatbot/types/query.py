from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from event_chatbot.types.events import EventCandidate

AllowedTimeOfDay = Literal["morning", "afternoon", "evening", "night"]


class QuerySpec(BaseModel):
    city: str | None = None
    raw_category_text: str | None = None
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    vibes: list[str] = Field(default_factory=list)
    date_text: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    time_of_day: AllowedTimeOfDay | None = None
    max_price: float | None = None
    radius_km: float | None = None
    hard_category_only: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None


class HardFilters(BaseModel):
    city: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    max_price: float | None = None
    statuses: list[str] = Field(default_factory=lambda: ["onsale", "scheduled", "unknown"])
    hard_category_filters: list[str] = Field(default_factory=list)


class NormalizedQuery(BaseModel):
    hard_filters: HardFilters
    city_slug: str | None = None
    category_boosts: list[str] = Field(default_factory=list)
    vibe_tags: list[str] = Field(default_factory=list)
    fts_terms: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, gt=0)
    candidate_limit: int = Field(default=200, gt=0)
    used_fts: bool = False
    fts_query: str | None = None


class SearchRequest(BaseModel):
    city: str | None = None
    q: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    max_price: float | None = None
    limit: int = Field(default=20, gt=0)


class RankedEvent(BaseModel):
    event: EventCandidate
    score: float
    lexical_score: float
    temporal_score: float
    price_score: float
    tag_overlap_score: float
