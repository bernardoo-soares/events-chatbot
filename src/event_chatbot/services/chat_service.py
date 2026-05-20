import sqlite3

from event_chatbot.db.connection import transaction
from event_chatbot.providers.llm import IntentExtractor, ResponseRenderer
from event_chatbot.repositories.chat_sessions import ChatSessionRepository
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.types.chat import ChatRequest, ChatResponse

MAX_CHAT_RESULTS = 5


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
        now = self.retrieval.clock()
        with transaction(self.conn):
            state = self.sessions.get_or_create(request.session_id, now)
            self.sessions.append_message(request.session_id, "user", request.message, now)
            spec = self.intent_extractor.extract_intent(request.message, state)

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
            results = self.retrieval.search(normalized)
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
