from typing import Protocol

from event_chatbot.types.ingestion import IngestionRequest, SourcePayload


class EventSourceProvider(Protocol):
    def fetch_events(self, request: IngestionRequest) -> list[SourcePayload]:
        ...

