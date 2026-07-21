from event_chatbot.db.connection import connect


def test_connect_creates_parent_directory(tmp_path) -> None:
    db_path = tmp_path / "nested" / "events.sqlite"

    conn = connect(str(db_path))
    conn.close()

    assert db_path.exists()


def test_connect_enables_concurrent_access_pragmas(tmp_path) -> None:
    conn = connect(str(tmp_path / "pragmas.sqlite"))
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        conn.close()

    assert journal_mode.lower() == "wal"
    assert busy_timeout == 5000

