import re
from dataclasses import dataclass
from typing import Literal

from event_chatbot.core.logging import get_logger
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import PrimaryIntent, QuerySpec, RequestIntent

OUT_OF_SCOPE_RESPONSE = (
    "I can help with event recommendations and plans in Lisbon or Madrid. "
    "Ask me for concerts, exhibitions, culture, nightlife, cheap plans, or weekend ideas."
)
CLARIFICATION_RESPONSE = (
    "I can help you find real events. What kind of plan are you looking for: music, "
    "exhibitions, theatre, nightlife, culture, or something relaxed?"
)
REQUEST_CONFIDENCE_THRESHOLD = 0.65

ScopeAction = Literal["retrieve", "clarify", "block"]


@dataclass(frozen=True)
class ScopeDecision:
    action: ScopeAction
    response: str | None
    reason: str

EVENT_TERMS = {
    "art",
    "arts",
    "cinema",
    "comedy",
    "concert",
    "concerts",
    "culture",
    "event",
    "events",
    "exhibition",
    "exhibitions",
    "festival",
    "festivals",
    "gig",
    "gigs",
    "live",
    "museum",
    "music",
    "nightlife",
    "party",
    "plan",
    "plans",
    "show",
    "shows",
    "tasting",
    "tastings",
    "theater",
    "theatre",
    "things to do",
    "tour",
    "tours",
    "wine tasting",
    "workshop",
    "workshops",
    "weekend ideas",
}

ACTIVITY_CONTEXT_TERMS = {
    "activity",
    "activities",
    "do",
    "go out",
    "idea",
    "ideas",
    "night out",
    "place",
    "places",
    "plan",
    "plans",
    "recommend",
    "recommendation",
    "something",
    "things to do",
}

FOOD_DRINK_ACTIVITY_TERMS = {
    "bar",
    "bars",
    "beer",
    "cocktail",
    "cocktails",
    "drink",
    "drinks",
    "food festival",
    "tapas",
    "tasting",
    "tastings",
    "wine",
    "wine tasting",
}

NON_EVENT_TERMS = {
    "forecast",
    "rain",
    "temperature",
    "umbrella",
    "weather",
    "wind",
    "stocks",
    "stock",
    "crypto",
    "news",
    "sports score",
    "score",
    "flight",
    "flights",
    "hotel",
    "hotels",
    "directions",
    "route",
    "traffic",
    "restaurant",
    "restaurants",
    "recipe",
    "code",
    "coding",
}

logger = get_logger(__name__)


def deterministic_request_intent(message: str) -> RequestIntent | None:
    normalized = " ".join(message.casefold().split())
    if not normalized:
        return RequestIntent(
            primary_intent="unknown",
            confidence=1.0,
            excluded_reason="The user message is empty.",
        )

    has_event_term = _contains_term(normalized, EVENT_TERMS)
    has_non_event_term = _contains_term(normalized, NON_EVENT_TERMS)
    has_activity_context = _contains_term(normalized, ACTIVITY_CONTEXT_TERMS)
    has_food_drink_activity = _contains_term(normalized, FOOD_DRINK_ACTIVITY_TERMS)
    if has_food_drink_activity and (has_activity_context or _has_time_language(normalized)):
        return RequestIntent(
            primary_intent="activity_plan",
            is_time_bound=_has_time_language(normalized),
            wants_real_world_activity=True,
            wants_catalog_event=False,
            activity_terms=_matched_terms(normalized, FOOD_DRINK_ACTIVITY_TERMS),
            confidence=0.95,
        )
    if has_non_event_term and not has_event_term and not has_activity_context:
        logger.info("Scope guard rejected non-event message message=%r", message)
        return RequestIntent(
            primary_intent=_non_event_intent(normalized),
            confidence=1.0,
            excluded_reason="The message contains an obvious non-event request.",
        )

    return None


def decide_scope(intent: RequestIntent, state: SessionState | None) -> ScopeDecision:
    if intent.confidence < REQUEST_CONFIDENCE_THRESHOLD:
        return ScopeDecision(
            action="clarify",
            response=CLARIFICATION_RESPONSE,
            reason="Request intent confidence is below the routing threshold.",
        )

    if intent.primary_intent in {"event_search", "activity_plan"}:
        return ScopeDecision(action="retrieve", response=None, reason="Event or activity request.")

    if intent.primary_intent == "venue_recommendation":
        if intent.wants_real_world_activity or intent.is_time_bound:
            return ScopeDecision(
                action="retrieve",
                response=None,
                reason="Venue request is framed as a time-bound local activity.",
            )
        return ScopeDecision(
            action="clarify",
            response=CLARIFICATION_RESPONSE,
            reason="Venue request is not clearly event-like.",
        )

    if intent.primary_intent in {"weather", "travel", "general_question"}:
        if intent.wants_real_world_activity or intent.wants_catalog_event:
            return ScopeDecision(
                action="retrieve",
                response=None,
                reason="Non-event topic is connected to finding a local activity.",
            )
        return ScopeDecision(
            action="block",
            response=OUT_OF_SCOPE_RESPONSE,
            reason=intent.excluded_reason or "Request is outside event recommendations.",
        )

    if state is not None and state.current_query is not None and intent.is_time_bound:
        return ScopeDecision(
            action="retrieve",
            response=None,
            reason="Ambiguous follow-up can reuse prior event-search state.",
        )

    return ScopeDecision(
        action="clarify",
        response=CLARIFICATION_RESPONSE,
        reason=intent.excluded_reason or "Request is too ambiguous to retrieve.",
    )


def has_explicit_event_language(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    return _contains_term(normalized, EVENT_TERMS)


def has_meaningful_query_signal(spec: QuerySpec) -> bool:
    return any(
        [
            spec.raw_category_text,
            spec.categories,
            spec.keywords,
            spec.vibes,
            spec.date_text,
            spec.date_preset,
            spec.date_day is not None and spec.date_month is not None,
            spec.date_from,
            spec.date_to,
            spec.relative_date_amount is not None and spec.relative_date_unit is not None,
            spec.time_of_day,
            spec.max_price is not None,
        ]
    )


def can_retrieve(
    *,
    message: str,
    spec: QuerySpec,
    state: SessionState | None,
) -> bool:
    if spec.needs_clarification:
        return False
    if has_meaningful_query_signal(spec):
        return True
    if has_explicit_event_language(message) and spec.city:
        return True
    return state is not None and state.current_query is not None


def _contains_term(normalized_message: str, terms: set[str]) -> bool:
    tokens = set(re.findall(r"\b[\w-]+\b", normalized_message))
    for term in terms:
        normalized_term = term.casefold()
        if " " in normalized_term:
            if normalized_term in normalized_message:
                return True
        elif normalized_term in tokens:
            return True
    return False


def _matched_terms(normalized_message: str, terms: set[str]) -> list[str]:
    return [term for term in sorted(terms) if _contains_term(normalized_message, {term})]


def _has_time_language(normalized_message: str) -> bool:
    time_terms = {
        "today",
        "tonight",
        "tomorrow",
        "weekend",
        "this week",
        "this weekend",
        "now",
        "soon",
    }
    return _contains_term(normalized_message, time_terms)


def _non_event_intent(normalized_message: str) -> PrimaryIntent:
    if _contains_term(normalized_message, {"weather", "forecast", "rain", "temperature", "wind"}):
        return "weather"
    if _contains_term(normalized_message, {"flight", "flights", "hotel", "hotels"}):
        return "travel"
    return "general_question"
