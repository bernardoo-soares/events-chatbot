import sqlite3
from importlib.resources import files


def initialize_database(conn: sqlite3.Connection) -> None:
    schema = files("event_chatbot.db").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
