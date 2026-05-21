import sqlite3
from importlib.resources import files

from event_chatbot.core.logging import get_logger

logger = get_logger(__name__)


def initialize_database(conn: sqlite3.Connection) -> None:
    logger.debug("Initializing database schema")
    schema = files("event_chatbot.db").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    logger.debug("Database schema initialized")
