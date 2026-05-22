from datetime import datetime

from pydantic import BaseModel


class EventEmbedding(BaseModel):
    event_id: int
    model: str
    embedding: list[float]
    embedded_text_hash: str
    created_at: datetime


class EventEmbeddingUpsert(BaseModel):
    event_id: int
    model: str
    embedding: list[float]
    embedded_text_hash: str


class EmbeddingBackfillSummary(BaseModel):
    model: str
    checked: int = 0
    embedded: int = 0
    skipped: int = 0
    errors: int = 0
