import sqlite3

from fastapi import HTTPException

from event_chatbot.core.logging import get_logger
from event_chatbot.db.connection import transaction
from event_chatbot.providers.llm import IntentExtractionError, IntentExtractor, ResponseRenderer
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.types.chat import ChatRequest, ChatResponse

MAX_CHAT_RESULTS = 5
logger = get_logger(__name__)


class ChatService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        sessions: ChatSessionRepository,
        intent_extractor: IntentExtractor,
        response_renderer: ResponseRenderer,
        retrieval: RetrievalService,
    ):
        self.conn = conn
        self.sessions = sessions
        self.intent_extractor = intent_extractor
        self.response_renderer = response_renderer
        self.retrieval = retrieval

    def chat(self, request: ChatRequest) -> ChatResponse:
        logger.info(
            "Chat request started session_id=%s message_chars=%s",
            request.session_id,
            len(request.message),
        )
        now = self.retrieval.clock()
        with transaction(self.conn):
            state = self.sessions.get_or_create(request.session_id, now)
            self.sessions.append_message(request.session_id, "user", request.message, now)
            try:
                spec = self.intent_extractor.extract_intent(request.message, state)
            except IntentExtractionError as exc:
                logger.exception(
                    "Chat request failed during intent extraction session_id=%s",
                    request.session_id,
                )
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            logger.info(
                "Chat intent extracted session_id=%s city=%s categories=%s "
                "keywords=%s needs_clarification=%s",
                request.session_id,
                spec.city,
                spec.categories,
                spec.keywords,
                spec.needs_clarification,
            )

            if spec.needs_clarification:
                assistant_message = spec.clarification_question or "Can you clarify your request?"
                self.sessions.append_message(
                    request.session_id,
                    "assistant",
                    assistant_message,
                    now,
                )
                return ChatResponse(
                    session_id=request.session_id,
                    assistant_message=assistant_message,
                    applied_filters={},
                    results=[],
                )

            normalized = self.retrieval.normalize(spec, previous=state)
            normalized.limit = min(normalized.limit, MAX_CHAT_RESULTS)
            logger.info(
                "Chat query normalized session_id=%s city=%s fts_terms=%s "
                "date_from=%s date_to=%s limit=%s",
                request.session_id,
                normalized.hard_filters.city,
                normalized.fts_terms,
                normalized.hard_filters.date_from,
                normalized.hard_filters.date_to,
                normalized.limit,
            )
            results = self.retrieval.search(normalized)
            logger.info(
                "Chat retrieval completed session_id=%s result_count=%s result_ids=%s",
                request.session_id,
                len(results),
                [result.event.id for result in results],
            )
            state.current_query = spec
            state.last_result_ids = [result.event.id for result in results]
            self.sessions.save_state(request.session_id, state, now)
            assistant_message = self.response_renderer.render_response(normalized, results)
            self.sessions.append_message(
                request.session_id,
                "assistant",
                assistant_message,
                now,
            )
            return ChatResponse(
                session_id=request.session_id,
                assistant_message=assistant_message,
                applied_filters=normalized.model_dump(mode="json"),
                results=results,
            )
