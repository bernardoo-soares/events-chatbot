import sqlite3

from fastapi import HTTPException

from event_chatbot.core.logging import get_logger
from event_chatbot.db.connection import transaction
from event_chatbot.providers.llm import (
    IntentExtractionError,
    IntentExtractor,
    RequestIntentClassifier,
    ResponseRenderer,
)
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.retrieval.scope import (
    CLARIFICATION_RESPONSE,
    can_retrieve,
    decide_scope,
    deterministic_request_intent,
)
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.types.chat import ChatRequest, ChatResponse
from event_chatbot.types.query import QuerySpec, RequestIntent

MAX_CHAT_RESULTS = 5
logger = get_logger(__name__)


class ChatService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        sessions: ChatSessionRepository,
        request_intent_classifier: RequestIntentClassifier,
        intent_extractor: IntentExtractor,
        response_renderer: ResponseRenderer,
        retrieval: RetrievalService,
    ):
        self.conn = conn
        self.sessions = sessions
        self.request_intent_classifier = request_intent_classifier
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

            request_intent = deterministic_request_intent(request.message)
            if request_intent is None:
                try:
                    request_intent = self.request_intent_classifier.classify_request_intent(
                        request.message,
                        state,
                    )
                except IntentExtractionError as exc:
                    logger.exception(
                        "Chat request failed during request-intent classification session_id=%s",
                        request.session_id,
                    )
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
            logger.info(
                "Chat request intent classified session_id=%s primary_intent=%s "
                "confidence=%.2f time_bound=%s activity=%s catalog_event=%s",
                request.session_id,
                request_intent.primary_intent,
                request_intent.confidence,
                request_intent.is_time_bound,
                request_intent.wants_real_world_activity,
                request_intent.wants_catalog_event,
            )

            scope_decision = decide_scope(request_intent, state)
            if scope_decision.action != "retrieve":
                logger.info(
                    "Chat request stopped by scope guard session_id=%s action=%s reason=%s",
                    request.session_id,
                    scope_decision.action,
                    scope_decision.reason,
                )
                assistant_message = scope_decision.response or CLARIFICATION_RESPONSE
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
            spec = _enrich_spec_from_request_intent(spec, request_intent)

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

            if not can_retrieve(message=request.message, spec=spec, state=state):
                logger.info(
                    "Chat request stopped by empty QuerySpec guard session_id=%s city=%s",
                    request.session_id,
                    spec.city,
                )
                self.sessions.append_message(
                    request.session_id,
                    "assistant",
                    CLARIFICATION_RESPONSE,
                    now,
                )
                return ChatResponse(
                    session_id=request.session_id,
                    assistant_message=CLARIFICATION_RESPONSE,
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


def _enrich_spec_from_request_intent(spec: QuerySpec, request_intent: RequestIntent) -> QuerySpec:
    updates: dict[str, object] = {}
    if spec.city is None and request_intent.city is not None:
        updates["city"] = request_intent.city
    if spec.date_text is None and request_intent.date_text is not None:
        updates["date_text"] = request_intent.date_text
    if not spec.keywords and request_intent.activity_terms:
        updates["keywords"] = request_intent.activity_terms
    if not updates:
        return spec
    return spec.model_copy(update=updates)
