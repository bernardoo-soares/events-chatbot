from typing import Protocol

from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent


class IntentExtractor(Protocol):
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        ...


class ResponseRenderer(Protocol):
    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        ...

