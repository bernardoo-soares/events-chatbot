from event_chatbot.db.connection import connect


def test_connect_creates_parent_directory(tmp_path) -> None:
    db_path = tmp_path / "nested" / "events.sqlite"

    conn = connect(str(db_path))
    conn.close()

    assert db_path.exists()

