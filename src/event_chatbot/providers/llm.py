from typing import Protocol

from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent, RequestIntent


class IntentExtractionError(RuntimeError):
    pass


class IntentExtractor(Protocol):
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        ...


class RequestIntentClassifier(Protocol):
    def classify_request_intent(self, message: str, state: SessionState | None) -> RequestIntent:
        ...


class ResponseRenderer(Protocol):
    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        ...
