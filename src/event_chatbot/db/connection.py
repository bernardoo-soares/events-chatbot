import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from event_chatbot.core.logging import get_logger

logger = get_logger(__name__)


def connect(database_path: str) -> sqlite3.Connection:
    logger.info("Opening SQLite connection path=%s", database_path)
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    logger.debug("SQLite connection ready path=%s", database_path)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
    except Exception:
        logger.exception("Rolling back database transaction")
        conn.rollback()
        raise
    else:
        conn.commit()
        logger.debug("Committed database transaction")
