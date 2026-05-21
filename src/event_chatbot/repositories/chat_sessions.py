import json
import sqlite3
from datetime import datetime

from event_chatbot.core.logging import get_logger
from event_chatbot.types.chat import MessageRole, SessionState
from event_chatbot.types.query import QuerySpec

logger = get_logger(__name__)


class ChatSessionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_or_create(self, session_id: str, now: datetime) -> SessionState:
        logger.debug("Loading chat session session_id=%s", session_id)
        row = self.conn.execute(
            "SELECT * FROM chat_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            logger.info("Creating chat session session_id=%s", session_id)
            now_text = now.isoformat()
            self.conn.execute(
                """
                INSERT INTO chat_sessions (
                    session_id,
                    created_at,
                    updated_at,
                    current_query_json,
                    last_result_ids_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, now_text, now_text, None, "[]"),
            )
            return SessionState(session_id=session_id, created_at=now, updated_at=now)
        logger.debug("Loaded existing chat session session_id=%s", session_id)
        return _session_state_from_row(row)

    def save_state(self, session_id: str, state: SessionState, now: datetime) -> None:
        logger.debug(
            "Saving chat session state session_id=%s last_result_count=%s has_current_query=%s",
            session_id,
            len(state.last_result_ids),
            state.current_query is not None,
        )
        current_query_json = (
            state.current_query.model_dump_json() if state.current_query is not None else None
        )
        self.conn.execute(
            """
            UPDATE chat_sessions
            SET updated_at = ?, current_query_json = ?, last_result_ids_json = ?
            WHERE session_id = ?
            """,
            (
                now.isoformat(),
                current_query_json,
                json.dumps(state.last_result_ids, separators=(",", ":")),
                session_id,
            ),
        )

    def append_message(
        self,
        session_id: str,
        role: MessageRole,
        message_text: str,
        now: datetime,
    ) -> None:
        logger.debug(
            "Appending chat message session_id=%s role=%s message_chars=%s",
            session_id,
            role,
            len(message_text),
        )
        self.conn.execute(
            """
            INSERT INTO chat_messages (session_id, role, message_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, message_text, now.isoformat()),
        )


def _session_state_from_row(row: sqlite3.Row) -> SessionState:
    current_query_json = row["current_query_json"]
    last_result_ids_json = row["last_result_ids_json"]
    current_query = (
        QuerySpec.model_validate_json(current_query_json) if current_query_json else None
    )
    last_result_ids = json.loads(last_result_ids_json) if last_result_ids_json else []
    return SessionState(
        session_id=row["session_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        current_query=current_query,
        last_result_ids=last_result_ids,
    )
