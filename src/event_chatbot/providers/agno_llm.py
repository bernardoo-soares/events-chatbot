import json
from typing import Any

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from pydantic import BaseModel, ValidationError

from event_chatbot.core.logging import get_logger
from event_chatbot.providers.llm import IntentExtractionError
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent, RequestIntent

logger = get_logger(__name__)

REQUEST_INTENT_INSTRUCTIONS = [
    "Extract the user's request intent for a local events and activity chatbot.",
    "Return only fields in the RequestIntent schema.",
    "Do not decide whether the app should block or retrieve. Python policy will decide.",
    "Classify conversation_role using the previous current_query only to understand whether the "
    "new user message depends on prior context.",
    "Use conversation_role='new_search' when the message contains a fresh request with its own "
    "activity, category, city, date, or vibe. New searches should usually have "
    "context_carryover=[].",
    "Use conversation_role='follow_up_refinement' when the message is incomplete without prior "
    "context and modifies one or two fields, for example 'what about tomorrow', 'make it cheaper', "
    "'under 25', 'only comedy', or 'something more relaxed'.",
    "Use conversation_role='follow_up_more_results' when the user asks for more, other options, "
    "alternatives, or similar results.",
    "Use conversation_role='follow_up_comparison' when the user asks about results already shown.",
    "Use conversation_role='ambiguous' when the relationship to prior context is unclear.",
    "Set context_carryover to exactly the previous query fields that should survive into this "
    "turn. Allowed values are city, date, budget, category, keywords, vibes.",
    "Do not carry fields contradicted or replaced by the new message. If the new message gives a "
    "different city, date, budget, category, keyword, or vibe, the new value wins.",
    "Use primary_intent='event_search' for explicit catalog events: concerts, exhibitions, "
    "theatre, cinema, festivals, workshops, tours, sports events, shows, talks, or parties.",
    "Use primary_intent='activity_plan' for local plans or things to do, even when the user "
    "does not use the word event.",
    "Use primary_intent='venue_recommendation' for restaurants, bars, clubs, places, or venues.",
    "Use primary_intent='weather' only when the user mainly asks for weather or forecast.",
    "Use primary_intent='travel' for hotels, flights, routes, transport, traffic, or directions.",
    "Use primary_intent='general_question' for news, facts, code, recipes, medical/legal advice, "
    "stocks, crypto, or unrelated requests.",
    "Use primary_intent='unknown' when the request is too vague.",
    "Set wants_real_world_activity=true when the user wants to go somewhere or do something "
    "locally, including date nights, cheap plans, relaxed plans, nightlife, drinking wine, "
    "drinks, tastings, rainy-day plans, or family activities.",
    "Set wants_catalog_event=true when the wording suggests ticketed/listed/scheduled events.",
    "Set is_time_bound=true for today, tonight, tomorrow, this week, this weekend, soon, now, "
    "or any explicit date/time.",
    "Extract city and date_text if present, but do not invent them.",
    "Put useful search words in activity_terms, for example wine, drinks, tasting, jazz, "
    "exhibition, relaxed, family, nightlife.",
    "Generic restaurant or bar listings are venue_recommendation, not event_search.",
    "Time-bound food/drink activities, tastings, nightlife plans, or event-like outings should "
    "set wants_real_world_activity=true.",
    "Weather-only requests should be weather with wants_real_world_activity=false.",
    "Weather plus 'what can I do' or 'events if it rains' should set "
    "wants_real_world_activity=true.",
    "Normalize known city names to the database spelling when extracting city: Lisboa -> Lisbon, "
    "Madri -> Madrid, Paris stays Paris.",
    "Example: 'What is the weather tomorrow?' -> "
    '{"primary_intent":"weather","conversation_role":"new_search","context_carryover":[],'
    '"is_time_bound":true,'
    '"wants_real_world_activity":false,"wants_catalog_event":false,'
    '"city":null,"date_text":"tomorrow","activity_terms":[],'
    '"excluded_reason":"The user asks only for weather.","confidence":0.98}',
    "Example: 'give me a place to drink wine today' -> "
    '{"primary_intent":"activity_plan","conversation_role":"new_search",'
    '"context_carryover":[],"is_time_bound":true,'
    '"wants_real_world_activity":true,"wants_catalog_event":false,'
    '"city":null,"date_text":"today","activity_terms":["wine","drinks"],'
    '"excluded_reason":null,"confidence":0.92}',
    "Example: 'best restaurants in Lisbon' -> "
    '{"primary_intent":"venue_recommendation","conversation_role":"new_search",'
    '"context_carryover":[],"is_time_bound":false,'
    '"wants_real_world_activity":false,"wants_catalog_event":false,'
    '"city":"Lisbon","date_text":null,"activity_terms":["restaurants"],'
    '"excluded_reason":"The user asks for generic venue listings.","confidence":0.88}',
    "Example: 'what can I do in Lisbon if it rains?' -> "
    '{"primary_intent":"activity_plan","conversation_role":"new_search",'
    '"context_carryover":[],"is_time_bound":false,'
    '"wants_real_world_activity":true,"wants_catalog_event":false,'
    '"city":"Lisbon","date_text":null,"activity_terms":["rainy day","indoor"],'
    '"excluded_reason":null,"confidence":0.90}',
    "Example with previous current_query 'Madrid under 25 euros': "
    "'I want something relaxed in Lisbon this weekend' -> "
    '{"primary_intent":"activity_plan","conversation_role":"new_search",'
    '"context_carryover":[],"is_time_bound":true,'
    '"wants_real_world_activity":true,"wants_catalog_event":false,'
    '"city":"Lisbon","date_text":"this weekend","activity_terms":["relaxed"],'
    '"excluded_reason":null,"confidence":0.90}',
    "Example with previous current_query 'comedy in Madrid under 25 euros': "
    "'what about tomorrow?' -> "
    '{"primary_intent":"activity_plan","conversation_role":"follow_up_refinement",'
    '"context_carryover":["city","budget","category","keywords","vibes"],'
    '"is_time_bound":true,"wants_real_world_activity":true,"wants_catalog_event":false,'
    '"city":null,"date_text":"tomorrow","activity_terms":[],'
    '"excluded_reason":null,"confidence":0.86}',
    "Example with previous current_query 'concerts in Lisbon this weekend': "
    "'make it under 25' -> "
    '{"primary_intent":"activity_plan","conversation_role":"follow_up_refinement",'
    '"context_carryover":["city","date","category","keywords","vibes"],'
    '"is_time_bound":false,"wants_real_world_activity":true,"wants_catalog_event":false,'
    '"city":null,"date_text":null,"activity_terms":[],'
    '"excluded_reason":null,"confidence":0.88}',
]

INTENT_INSTRUCTIONS = [
    "Extract event-search intent from the user message.",
    "This agent runs only after a separate scope classifier has accepted the message "
    "as event-related.",
    "Return only fields in the QuerySpec schema.",
    "Do not write SQL.",
    "Do not invent event data.",
    "Use categories as suggestions, not final hard filters.",
    "Leave categories empty for broad requests like 'events' or 'things to do'.",
    "Only set categories when the user names a specific event type.",
    "Extract explicit city names from the message when present.",
    "Do not convert relative date phrases to guessed calendar dates.",
    "For relative dates like 'in one month', 'next month', 'in two weeks', or "
    "'in 10 days', keep date_text as the original phrase and set "
    "relative_date_amount plus relative_date_unit. Use date_window_days=4 unless the user "
    "asks for a different span.",
    "For 'next month', use relative_date_amount=1 and relative_date_unit='month'.",
    "For 'in one month', use relative_date_amount=1 and relative_date_unit='month'.",
    "For 'in two weeks', use relative_date_amount=2 and relative_date_unit='week'.",
    "For 'in 10 days', use relative_date_amount=10 and relative_date_unit='day'.",
    "For broad upcoming ranges like 'next 30 days', leave date fields empty.",
    "Set hard_category_only=true only when the user explicitly says only/just/no other categories.",
    "Set needs_clarification=true only when retrieval cannot proceed safely.",
    "Normalize known city names to the database spelling: Lisboa -> Lisbon, Madri -> Madrid, "
    "Paris stays Paris.",
]

RESPONSE_INSTRUCTIONS = [
    "You are formatting already-retrieved event rows for a user-facing chat UI.",
    "Use only the supplied event rows.",
    "Use exactly the supplied event order.",
    "Do not reorder, add, remove, or replace events.",
    "Do not add venues, prices, dates, URLs, or event facts that are not present.",
    "Do not create reasons, summaries, vibes, opinions, or descriptions.",
    "Do not paraphrase event descriptions.",
    "Return at most 5 events.",
    "Use plain text only.",
    "Do not use Markdown headings, Markdown tables, bold markers, asterisks, or emojis.",
    "Use one short opening sentence.",
    "For each event, output exactly this format:",
    "1. {title}",
    "   Date: {start_at} or {start_at} - {end_at}",
    "   Venue: {venue_name or Venue not specified}",
    "   City: {city}",
    "If results are empty, say exactly:",
    "No matching events were found. Try changing the city, date, category, or budget.",
]


class AgnoIntentExtractor:
    def __init__(self, model_id: str, api_key: str):
        self.model_id = model_id
        self.request_intent_agent = Agent(
            model=OpenAIResponses(id=model_id, api_key=api_key),
            output_schema=RequestIntent,
            instructions=REQUEST_INTENT_INSTRUCTIONS,
        )
        self.agent = Agent(
            model=OpenAIResponses(id=model_id, api_key=api_key),
            output_schema=QuerySpec,
            instructions=INTENT_INSTRUCTIONS,
        )

    def classify_request_intent(self, message: str, state: SessionState | None) -> RequestIntent:
        logger.info(
            "Starting LLM request-intent classification model=%s "
            "message_chars=%s has_previous_query=%s",
            self.model_id,
            len(message),
            state is not None and state.current_query is not None,
        )
        payload: dict[str, Any] = {"user_message": message}
        if state is not None and state.current_query is not None:
            payload["current_query"] = state.current_query.model_dump(mode="json")
        try:
            response = self.request_intent_agent.run(json.dumps(payload, ensure_ascii=True))
        except Exception as exc:
            error_message = (
                f"LLM request-intent classification failed: {type(exc).__name__}: {exc}"
            )
            logger.exception(
                "LLM request-intent classification call failed model=%s",
                self.model_id,
            )
            raise IntentExtractionError(error_message) from exc
        content = getattr(response, "content", response)
        try:
            request_intent = _parse_request_intent(content)
        except ValidationError as exc:
            logger.exception(
                "LLM returned invalid request-intent payload type=%s value=%r",
                type(content).__name__,
                content,
            )
            raise IntentExtractionError(
                f"LLM returned invalid request-intent payload: {content!r}"
            ) from exc
        logger.info(
            "LLM request-intent classification succeeded primary_intent=%s confidence=%.2f",
            request_intent.primary_intent,
            request_intent.confidence,
        )
        return request_intent

    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        logger.info(
            "Starting LLM intent extraction model=%s message_chars=%s has_previous_query=%s",
            self.model_id,
            len(message),
            state is not None and state.current_query is not None,
        )
        payload: dict[str, Any] = {"user_message": message}
        if state is not None and state.current_query is not None:
            payload["current_query"] = state.current_query.model_dump(mode="json")
        try:
            response = self.agent.run(json.dumps(payload, ensure_ascii=True))
        except Exception as exc:
            error_message = f"LLM intent extraction failed: {type(exc).__name__}: {exc}"
            logger.exception("LLM intent extraction call failed model=%s", self.model_id)
            raise IntentExtractionError(error_message) from exc
        content = getattr(response, "content", response)
        try:
            spec = _parse_query_spec(content)
        except ValidationError as exc:
            logger.exception(
                "LLM returned invalid intent payload type=%s value=%r",
                type(content).__name__,
                content,
            )
            error_message = f"LLM returned invalid intent payload: {content!r}"
            raise IntentExtractionError(error_message) from exc
        logger.info(
            "LLM intent extraction succeeded city=%s text_query=%s needs_clarification=%s",
            spec.city,
            " ".join(spec.keywords),
            spec.needs_clarification,
        )
        return spec


def _parse_request_intent(content: Any) -> RequestIntent:
    if isinstance(content, RequestIntent):
        return content
    if isinstance(content, BaseModel):
        return RequestIntent.model_validate(content.model_dump())
    return RequestIntent.model_validate(content)


def _parse_query_spec(content: Any) -> QuerySpec:
    if isinstance(content, QuerySpec):
        return content
    if isinstance(content, BaseModel):
        return QuerySpec.model_validate(content.model_dump())
    return QuerySpec.model_validate(content)


class AgnoResponseRenderer:
    def __init__(self, model_id: str, api_key: str):
        self.model_id = model_id
        self.agent = Agent(
            model=OpenAIResponses(id=model_id, api_key=api_key),
            instructions=RESPONSE_INSTRUCTIONS,
        )

    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        logger.info(
            "Starting LLM response rendering model=%s city=%s event_count=%s",
            self.model_id,
            query.hard_filters.city,
            len(events),
        )
        payload = {
            "query": query.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in events],
        }
        response = self.agent.run(
            json.dumps(payload, ensure_ascii=True),
        )
        content = getattr(response, "content", response)
        logger.info("LLM response rendering completed model=%s", self.model_id)
        return str(content)
