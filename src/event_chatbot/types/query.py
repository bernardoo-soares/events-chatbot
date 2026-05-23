from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from event_chatbot.types.events import EventCandidate

AllowedTimeOfDay = Literal["morning", "afternoon", "evening", "night"]
RelativeDateUnit = Literal["day", "week", "month"]
PrimaryIntent = Literal[
    "event_search",
    "activity_plan",
    "venue_recommendation",
    "weather",
    "travel",
    "general_question",
    "unknown",
]
ConversationRole = Literal[
    "new_search",
    "follow_up_refinement",
    "follow_up_more_results",
    "follow_up_comparison",
    "ambiguous",
]
CarryoverField = Literal["city", "date", "budget", "category", "keywords", "vibes"]


class RequestIntent(BaseModel):
    primary_intent: PrimaryIntent
    conversation_role: ConversationRole = "new_search"
    context_carryover: list[CarryoverField] = Field(default_factory=list)
    is_time_bound: bool = False
    wants_real_world_activity: bool = False
    wants_catalog_event: bool = False
    city: str | None = None
    date_text: str | None = None
    activity_terms: list[str] = Field(default_factory=list)
    excluded_reason: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class QuerySpec(BaseModel):
    is_event_search: bool = True
    out_of_scope_reason: str | None = None
    city: str | None = None
    raw_category_text: str | None = None
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    vibes: list[str] = Field(default_factory=list)
    date_text: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    relative_date_amount: int | None = Field(default=None, ge=1)
    relative_date_unit: RelativeDateUnit | None = None
    date_window_days: int | None = Field(default=None, ge=0)
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
    semantic_terms: list[str] = Field(default_factory=list)
    carryover_fields: list[CarryoverField] = Field(default_factory=list)


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
    semantic_score: float = 0.5
    temporal_score: float
    price_score: float
    tag_overlap_score: float
