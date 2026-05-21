from typing import Annotated

from fastapi import APIRouter, Depends

from event_chatbot.api.dependencies import get_chat_service
from event_chatbot.core.logging import get_logger
from event_chatbot.services.chat_service import ChatService
from event_chatbot.types.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    logger.info(
        "Chat endpoint received session_id=%s message_chars=%s",
        request.session_id,
        len(request.message),
    )
    response = service.chat(request)
    logger.info(
        "Chat endpoint returning session_id=%s assistant_chars=%s result_count=%s",
        response.session_id,
        len(response.assistant_message),
        len(response.results),
    )
    return response
