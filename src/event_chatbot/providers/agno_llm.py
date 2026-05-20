import json
from typing import Any

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from pydantic import BaseModel

from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent

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
    "Answer using only the supplied event rows.",
    "Do not add venues, prices, dates, URLs, or event facts that are not present.",
    "If results are empty, say no matching events were found and suggest changing filters.",
    "Recommend at most 5 events.",
    "Keep the answer concise, friendly, and easy to scan.",
    "Use plain text, not Markdown tables.",
    "Avoid markdown emphasis markers like **bold**.",
    "For each event, include only title, date, venue, and one short reason when available.",
]


class AgnoIntentExtractor:
    def __init__(self, model_id: str, api_key: str):
        self.agent = Agent(
            model=OpenAIResponses(id=model_id, api_key=api_key),
            output_schema=QuerySpec,
            instructions=INTENT_INSTRUCTIONS,
        )

    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        payload: dict[str, Any] = {"user_message": message}
        if state is not None and state.current_query is not None:
            payload["current_query"] = state.current_query.model_dump(mode="json")
        response = self.agent.run(json.dumps(payload, ensure_ascii=True))
        content = getattr(response, "content", response)
        if isinstance(content, QuerySpec):
            return content
        if isinstance(content, BaseModel):
            return QuerySpec.model_validate(content.model_dump())
        return QuerySpec.model_validate(content)


class AgnoResponseRenderer:
    def __init__(self, model_id: str, api_key: str):
        self.agent = Agent(
            model=OpenAIResponses(id=model_id, api_key=api_key),
            instructions=RESPONSE_INSTRUCTIONS,
        )

    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        payload = {
            "query": query.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in events],
        }
        response = self.agent.run(
            json.dumps(payload, ensure_ascii=True),
        )
        content = getattr(response, "content", response)
        return str(content)
