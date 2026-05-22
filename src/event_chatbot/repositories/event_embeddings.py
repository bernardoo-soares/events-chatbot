import json
import sqlite3
from datetime import datetime

from event_chatbot.core.logging import get_logger
from event_chatbot.types.embeddings import EventEmbedding, EventEmbeddingUpsert

logger = get_logger(__name__)


class EventEmbeddingRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_many(self, embeddings: list[EventEmbeddingUpsert], now: datetime) -> None:
        logger.info("Upserting event embeddings count=%s", len(embeddings))
        now_text = now.isoformat()
        for embedding in embeddings:
            self.conn.execute(
                """
                INSERT INTO event_embeddings (
                    event_id,
                    model,
                    embedding_json,
                    embedded_text_hash,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    model = excluded.model,
                    embedding_json = excluded.embedding_json,
                    embedded_text_hash = excluded.embedded_text_hash,
                    created_at = excluded.created_at
                """,
                (
                    embedding.event_id,
                    embedding.model,
                    json.dumps(embedding.embedding, separators=(",", ":")),
                    embedding.embedded_text_hash,
                    now_text,
                ),
            )

    def get_by_event_ids(self, event_ids: list[int], model: str) -> dict[int, list[float]]:
        if not event_ids:
            return {}
        placeholders = ", ".join(["?"] * len(event_ids))
        rows = self.conn.execute(
            f"""
            SELECT event_id, embedding_json
            FROM event_embeddings
            WHERE model = ? AND event_id IN ({placeholders})
            """,
            [model, *event_ids],
        ).fetchall()
        embeddings: dict[int, list[float]] = {}
        for row in rows:
            parsed = json.loads(row["embedding_json"])
            if isinstance(parsed, list):
                embeddings[int(row["event_id"])] = [float(value) for value in parsed]
        return embeddings

    def get_metadata_by_event_ids(self, event_ids: list[int]) -> dict[int, EventEmbedding]:
        if not event_ids:
            return {}
        placeholders = ", ".join(["?"] * len(event_ids))
        rows = self.conn.execute(
            f"""
            SELECT event_id, model, embedding_json, embedded_text_hash, created_at
            FROM event_embeddings
            WHERE event_id IN ({placeholders})
            """,
            event_ids,
        ).fetchall()
        return {int(row["event_id"]): _embedding_from_row(row) for row in rows}


def _embedding_from_row(row: sqlite3.Row) -> EventEmbedding:
    parsed = json.loads(row["embedding_json"])
    return EventEmbedding(
        event_id=int(row["event_id"]),
        model=row["model"],
        embedding=[float(value) for value in parsed],
        embedded_text_hash=row["embedded_text_hash"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
