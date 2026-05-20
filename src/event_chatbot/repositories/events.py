import sqlite3
from datetime import datetime

from event_chatbot.retrieval.query_builder import build_candidate_query
from event_chatbot.types.events import Event, EventCandidate
from event_chatbot.types.ingestion import SourceEvent, UpsertSummary
from event_chatbot.types.query import NormalizedQuery

EVENT_COLUMNS = (
    "source",
    "source_event_id",
    "title",
    "description",
    "city",
    "venue_name",
    "category",
    "subcategory",
    "start_at",
    "end_at",
    "timezone",
    "min_price",
    "max_price",
    "currency",
    "status",
    "url",
    "image_url",
    "latitude",
    "longitude",
)


class EventRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_many(self, events: list[SourceEvent], now: datetime) -> UpsertSummary:
        summary = UpsertSummary()
        now_text = _datetime_to_text(now)

        for event in events:
            existing = self.conn.execute(
                "SELECT id FROM events WHERE source = ? AND source_event_id = ?",
                (event.source, event.source_event_id),
            ).fetchone()
            values = _source_event_values(event)
            if existing is None:
                self.conn.execute(
                    f"""
                    INSERT INTO events (
                        {", ".join(EVENT_COLUMNS)},
                        ingested_at,
                        last_seen_at
                    )
                    VALUES ({", ".join(["?"] * (len(EVENT_COLUMNS) + 2))})
                    """,
                    (*values, now_text, now_text),
                )
                summary.inserted += 1
            else:
                assignments = ", ".join(f"{column} = ?" for column in EVENT_COLUMNS)
                self.conn.execute(
                    f"""
                    UPDATE events
                    SET {assignments}, last_seen_at = ?
                    WHERE id = ?
                    """,
                    (*values, now_text, existing["id"]),
                )
                summary.updated += 1

        return summary

    def search_candidates(self, query: NormalizedQuery) -> list[EventCandidate]:
        sql, params = build_candidate_query(query)
        rows = self.conn.execute(sql, params).fetchall()
        return [_candidate_from_row(row) for row in rows]

    def get_by_ids(self, ids: list[int]) -> list[Event]:
        if not ids:
            return []
        placeholders = ", ".join(["?"] * len(ids))
        rows = self.conn.execute(
            f"SELECT * FROM events WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        events_by_id = {_event_from_row(row).id: _event_from_row(row) for row in rows}
        return [events_by_id[event_id] for event_id in ids if event_id in events_by_id]

def _source_event_values(event: SourceEvent) -> tuple[object, ...]:
    return (
        event.source,
        event.source_event_id,
        event.title,
        event.description,
        event.city,
        event.venue_name,
        event.category,
        event.subcategory,
        _datetime_to_text(event.start_at),
        _datetime_to_text(event.end_at),
        event.timezone,
        event.min_price,
        event.max_price,
        event.currency,
        event.status,
        event.url,
        event.image_url,
        event.latitude,
        event.longitude,
    )


def _candidate_from_row(row: sqlite3.Row) -> EventCandidate:
    data = dict(row)
    return EventCandidate(**_parse_event_data(data))


def _event_from_row(row: sqlite3.Row) -> Event:
    return Event(**_parse_event_data(dict(row)))


def _parse_event_data(data: dict) -> dict:
    for field in ("start_at", "end_at", "ingested_at", "last_seen_at"):
        if data.get(field) is not None:
            data[field] = datetime.fromisoformat(data[field])
    return data


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
