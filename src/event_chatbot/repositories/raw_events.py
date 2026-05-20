import json
import sqlite3
from datetime import datetime

from event_chatbot.types.ingestion import SourcePayload, UpsertSummary


class RawEventRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_many(self, payloads: list[SourcePayload], fetched_at: datetime) -> UpsertSummary:
        summary = UpsertSummary()
        fetched_at_text = fetched_at.isoformat()

        for payload in payloads:
            existing = self.conn.execute(
                "SELECT id FROM raw_events WHERE source = ? AND source_event_id = ?",
                (payload.source, payload.source_event_id),
            ).fetchone()
            payload_json = json.dumps(payload.payload, separators=(",", ":"), sort_keys=True)
            if existing is None:
                self.conn.execute(
                    """
                    INSERT INTO raw_events (source, source_event_id, payload_json, fetched_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (payload.source, payload.source_event_id, payload_json, fetched_at_text),
                )
                summary.inserted += 1
            else:
                self.conn.execute(
                    """
                    UPDATE raw_events
                    SET payload_json = ?, fetched_at = ?
                    WHERE id = ?
                    """,
                    (payload_json, fetched_at_text, existing["id"]),
                )
                summary.updated += 1

        return summary

