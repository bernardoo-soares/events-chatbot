from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from event_chatbot.types.query import QuerySpec, RankedEvent

MessageRole = Literal["user", "assistant", "system", "tool"]


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    assistant_message: str
    applied_filters: dict = Field(default_factory=dict)
    results: list[RankedEvent] = Field(default_factory=list)


class ChatMessage(BaseModel):
    id: int
    session_id: str
    role: MessageRole
    message_text: str
    created_at: datetime


class SessionState(BaseModel):
    session_id: str
    created_at: datetime
    updated_at: datetime
    current_query: QuerySpec | None = None
    last_result_ids: list[int] = Field(default_factory=list)

