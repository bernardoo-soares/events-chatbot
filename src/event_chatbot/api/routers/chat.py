from typing import Annotated

from fastapi import APIRouter, Depends

from event_chatbot.api.dependencies import get_chat_service
from event_chatbot.services.chat_service import ChatService
from event_chatbot.types.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    return service.chat(request)
