PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    city TEXT,
    venue_name TEXT,
    category TEXT,
    subcategory TEXT,
    start_at TEXT NOT NULL,
    end_at TEXT,
    timezone TEXT,
    min_price REAL,
    max_price REAL,
    currency TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    url TEXT,
    image_url TEXT,
    latitude REAL,
    longitude REAL,
    ingested_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (source, source_event_id)
);

CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE (source, source_event_id)
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    current_query_json TEXT,
    last_result_ids_json TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    message_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_embeddings (
    event_id INTEGER PRIMARY KEY,
    model TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    embedded_text_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    title,
    description,
    city,
    venue_name,
    category,
    subcategory,
    content='events',
    content_rowid='id'
);

CREATE INDEX IF NOT EXISTS idx_events_source_event
    ON events (source, source_event_id);

CREATE INDEX IF NOT EXISTS idx_events_city_start
    ON events (city, start_at);

CREATE INDEX IF NOT EXISTS idx_events_category_start
    ON events (category, start_at);

CREATE INDEX IF NOT EXISTS idx_events_status_start
    ON events (status, start_at);

CREATE INDEX IF NOT EXISTS idx_events_price
    ON events (min_price, max_price);

CREATE INDEX IF NOT EXISTS idx_raw_events_source_event
    ON raw_events (source, source_event_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON chat_messages (session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_event_embeddings_model
    ON event_embeddings (model);

CREATE TRIGGER IF NOT EXISTS events_after_insert_sync_fts
AFTER INSERT ON events
BEGIN
    INSERT INTO events_fts(rowid, title, description, city, venue_name, category, subcategory)
    VALUES (new.id, new.title, new.description, new.city, new.venue_name, new.category, new.subcategory);
END;

CREATE TRIGGER IF NOT EXISTS events_after_delete_sync_fts
AFTER DELETE ON events
BEGIN
    INSERT INTO events_fts(events_fts, rowid, title, description, city, venue_name, category, subcategory)
    VALUES ('delete', old.id, old.title, old.description, old.city, old.venue_name, old.category, old.subcategory);
END;

CREATE TRIGGER IF NOT EXISTS events_after_update_sync_fts
AFTER UPDATE ON events
BEGIN
    INSERT INTO events_fts(events_fts, rowid, title, description, city, venue_name, category, subcategory)
    VALUES ('delete', old.id, old.title, old.description, old.city, old.venue_name, old.category, old.subcategory);

    INSERT INTO events_fts(rowid, title, description, city, venue_name, category, subcategory)
    VALUES (new.id, new.title, new.description, new.city, new.venue_name, new.category, new.subcategory);
END;
