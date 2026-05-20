import sqlite3

from event_chatbot.db.connection import connect, transaction
from event_chatbot.db.migrations import initialize_database


def test_initialize_database_creates_expected_tables() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_database(conn)

    table_names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
    }

    assert "events" in table_names
    assert "raw_events" in table_names
    assert "chat_sessions" in table_names
    assert "chat_messages" in table_names
    assert "events_fts" in table_names


def test_fts_triggers_sync_insert_update_delete() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)

    conn.execute(
        """
        INSERT INTO events (
            source,
            source_event_id,
            title,
            description,
            city,
            venue_name,
            category,
            subcategory,
            start_at,
            status,
            ingested_at,
            last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ticketmaster",
            "event-1",
            "Lisbon Jazz Night",
            "Live jazz and cocktails",
            "Lisbon",
            "Blue Note Lisboa",
            "music",
            "jazz",
            "2026-05-20T21:00:00+01:00",
            "onsale",
            "2026-05-19T23:00:00+01:00",
            "2026-05-19T23:00:00+01:00",
        ),
    )

    inserted = conn.execute(
        "SELECT rowid, title FROM events_fts WHERE events_fts MATCH ?",
        ("jazz",),
    ).fetchone()
    assert inserted is not None
    event_id = inserted["rowid"]
    assert inserted["title"] == "Lisbon Jazz Night"

    conn.execute(
        "UPDATE events SET title = ?, description = ?, subcategory = ? WHERE id = ?",
        ("Lisbon Rock Night", "Guitar-driven rock show", "rock", event_id),
    )

    old_match = conn.execute(
        "SELECT rowid FROM events_fts WHERE events_fts MATCH ?",
        ("jazz",),
    ).fetchone()
    new_match = conn.execute(
        "SELECT rowid, title FROM events_fts WHERE events_fts MATCH ?",
        ("rock",),
    ).fetchone()

    assert old_match is None
    assert new_match is not None
    assert new_match["title"] == "Lisbon Rock Night"

    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))

    deleted = conn.execute(
        "SELECT rowid FROM events_fts WHERE events_fts MATCH ?",
        ("rock",),
    ).fetchone()
    assert deleted is None


def test_connection_enables_foreign_keys_and_transaction_rolls_back(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = connect(str(db_path))
    initialize_database(conn)

    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, message_text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                ("missing-session", "user", "hello", "2026-05-19T23:00:00+01:00"),
            )
    except sqlite3.IntegrityError:
        pass

    count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
    assert count == 0
