import json
from typing import Any

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from pydantic import BaseModel, ValidationError

from event_chatbot.core.logging import get_logger
from event_chatbot.providers.llm import IntentExtractionError
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent

logger = get_logger(__name__)

INTENT_INSTRUCTIONS = [
    "Extract event-search intent from the user message.",
    "Return only fields in the QuerySpec schema.",
    "Do not write SQL.",
    "Do not invent event data.",
    "Use categories as suggestions, not final hard filters.",
    "Leave categories empty for broad requests like 'events' or 'things to do'.",
    "Only set categories when the user names a specific event type.",
    "Extract explicit city names from the message when present.",
    "Do not convert relative date phrases to guessed calendar dates.",
    "For broad upcoming ranges like 'next 30 days', leave date fields empty.",
    "Set hard_category_only=true only when the user explicitly says only/just/no other categories.",
    "Set needs_clarification=true only when retrieval cannot proceed safely.",
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
        self.agent = Agent(
            model=OpenAIResponses(id=model_id, api_key=api_key),
            output_schema=QuerySpec,
            instructions=INTENT_INSTRUCTIONS,
        )

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
        if isinstance(content, QuerySpec):
            logger.info(
                "LLM intent extraction succeeded city=%s text_query=%s needs_clarification=%s",
                content.city,
                " ".join(content.keywords),
                content.needs_clarification,
            )
            return content
        if isinstance(content, BaseModel):
            spec = QuerySpec.model_validate(content.model_dump())
            logger.info(
                "LLM intent extraction succeeded city=%s text_query=%s needs_clarification=%s",
                spec.city,
                " ".join(spec.keywords),
                spec.needs_clarification,
            )
            return spec
        try:
            spec = QuerySpec.model_validate(content)
            logger.info(
                "LLM intent extraction succeeded city=%s text_query=%s needs_clarification=%s",
                spec.city,
                " ".join(spec.keywords),
                spec.needs_clarification,
            )
            return spec
        except ValidationError as exc:
            logger.exception(
                "LLM returned invalid intent payload type=%s value=%r",
                type(content).__name__,
                content,
            )
            error_message = f"LLM returned invalid intent payload: {content!r}"
            raise IntentExtractionError(error_message) from exc


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
