from typing import Protocol

from event_chatbot.types.ingestion import IngestionRequest, SourcePayload


class EventSourceProvider(Protocol):
    source: str

    def fetch_events(self, request: IngestionRequest) -> list[SourcePayload]:
        ...
