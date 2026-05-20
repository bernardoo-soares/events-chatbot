# Architecture

## 1. Goal

Build a small FastAPI chatbot for local event discovery.

The core product requirement is that recommendations must be grounded in real event data stored in a local database. The chatbot can understand natural language and answer conversationally, but it must not invent events, write SQL directly, or fetch live web data during a chat request.

The system is best understood as a catalog-search chatbot:

```text
free-form user message
-> structured intent
-> deterministic normalization
-> SQLite + FTS retrieval
-> deterministic ranking
-> grounded conversational response
```

## 2. High-Level Architecture

```text
Ticketmaster Discovery API
AgendaLX API
        |
        v
ETL ingestion service
        |
        v
SQLite application database
  - events
  - raw_events
  - chat_sessions
  - chat_messages
  - events_fts
        ^
        |
Retrieval service + ranking engine
        ^
        |
Agno conversational layer
        ^
        |
FastAPI endpoints
```

The LLM layer is intentionally narrow. Agno is used to communicate with an external LLM provider and structure the conversational workflow. The retrieval engine remains deterministic Python code.

## 3. Main Components

### FastAPI

FastAPI exposes the public HTTP API:

- `POST /chat`: receive a session id and user message, then return a grounded assistant response.
- `POST /ingest`: manually trigger event ingestion from a configured source.
- `GET /events/search`: deterministic debug endpoint for checking retrieval without the chatbot.
- `GET /health`: health check.

### Agno

Agno sits in the conversational layer.

It is used for:

- Natural-language intent extraction into `QuerySpec`.
- Optional clarification-question generation.
- Grounded response rendering from returned DB rows.

It is not used for:

- Event ingestion.
- SQL generation.
- Final recommendation ranking.
- Live web/event search during chat.

Agno still needs an external model provider behind it, such as OpenAI or Vertex/Gemini. For the initial implementation, the expected environment variables are:

```text
OPENAI_API_KEY=...
TICKETMASTER_API_KEY=...
AGENDALX_BASE_URL=...
```

### Ticketmaster Discovery API

Ticketmaster is the first event-data source.

The API is used only by ingestion jobs, not by the chat request path. This keeps chat answers grounded in the local database and avoids mixing live external API behavior with retrieval behavior.

Future sources such as Eventbrite, PredictHQ, Bandsintown, or OpenAgenda can be added later because the DB schema stores `source` and `source_event_id`.

### AgendaLX API

AgendaLX is the Lisbon cultural-event source.

It is used only by ingestion jobs, not by chat. The provider calls the public AgendaLX API with pagination:

```text
https://www.agendalx.pt/wp-json/agendalx/v1/events?per_page=100&page=1
```

AgendaLX events are normalized into the same `SourceEvent` contract as Ticketmaster. The provider stores:

- `source="agendalx"`
- `source_event_id=str(id)`
- `city="Lisbon"`
- `timezone="Europe/Lisbon"`
- `status="scheduled"`

AgendaLX ingestion keeps only current or future events. Long-running events are kept if `LastDate` is today or later.

### SQLite

SQLite is the local application database for the MVP.

It stores:

- Normalized event records.
- Raw Ticketmaster payloads.
- Explicit per-session search state.
- Chat message audit trail.
- Full-text search index through SQLite FTS5.

SQLite is chosen because it is easy to run locally and strong enough for the challenge scope.

## 4. Ingestion Workflow

Ingestion is offline or manually triggered. It does not run inside `/chat`.

```text
POST /ingest
or
python -m app.etl.ingest_events
        |
        v
selected event provider
Ticketmaster Discovery API or AgendaLX API
        |
        v
store raw payload in raw_events
        |
        v
normalize into events
        |
        v
upsert by (source, source_event_id)
        |
        v
sync events_fts
```

For the MVP, ingestion should be synchronous enough to return a clear summary:

```json
{
  "source": "agendalx",
  "city": "Lisbon",
  "fetched": 120,
  "inserted": 80,
  "updated": 40,
  "errors": 0
}
```

Background scheduled ingestion can be added later, but the initial system should use a manual endpoint and/or CLI command.

## 5. Chat Workflow

The chat path only queries the local database.

```text
POST /chat
body: { "session_id": "...", "message": "..." }
        |
        v
load chat_sessions.current_query_json
        |
        v
Agno intent agent extracts QuerySpec
        |
        v
merge QuerySpec with prior session search state
        |
        v
normalize into NormalizedQuery
        |
        v
build SQL hard filters + FTS5 query
        |
        v
fetch bounded candidate set from SQLite
        |
        v
rerank candidates deterministically in Python
        |
        v
save updated search state and last result ids
        |
        v
Agno response agent formats grounded rows
        |
        v
return assistant response
```

The response may include:

```json
{
  "session_id": "abc-123",
  "assistant_message": "Here are a few live jazz options in Lisbon tonight...",
  "applied_filters": {},
  "results": []
}
```

## 6. Intent And Normalization

The LLM does not output SQL. It outputs a business-level intent object called `QuerySpec`.

`QuerySpec` is the bridge between free-form language and deterministic retrieval.

Current draft:

```python
class QuerySpec(BaseModel):
    city: str | None = None
    raw_category_text: str | None = None
    categories: list[str] = []
    keywords: list[str] = []
    vibes: list[str] = []
    date_text: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    time_of_day: Literal["morning", "afternoon", "evening", "night"] | None = None
    max_price: float | None = None
    radius_km: float | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None
```

The LLM can freely interpret user language, but the application validates and normalizes the output before retrieval.

Example user input:

```text
I want a chill gig with drinks in Lisbon tonight under 30 euros
```

Possible `QuerySpec`:

```json
{
  "city": "Lisbon",
  "raw_category_text": "chill gig with drinks",
  "categories": ["music", "nightlife"],
  "keywords": ["gig", "drinks"],
  "vibes": ["chill"],
  "date_text": "tonight",
  "time_of_day": "evening",
  "max_price": 30,
  "needs_clarification": false,
  "clarification_question": null
}
```

Then deterministic Python creates a `NormalizedQuery`.

Example:

```json
{
  "city_slug": "lisbon",
  "hard_filters": {
    "city": "Lisbon",
    "date_from": "2026-05-19T18:00:00+01:00",
    "date_to": "2026-05-19T23:59:59+01:00",
    "max_price": 30,
    "status": ["onsale", "unknown"]
  },
  "category_boosts": ["music", "nightlife"],
  "hard_category_filters": [],
  "fts_terms": ["gig", "drinks", "chill", "live music", "bar"],
  "vibe_tags": ["chill", "casual", "relaxed"],
  "limit": 200
}
```

Important rule: categories are usually ranking boosts, not hard filters. A hard category filter is used only when the user is explicit, for example "only sports events".

## 7. Retrieval Strategy

Retrieval has two stages:

1. SQL hard filters for constraints that should not be fuzzy.
2. FTS5 lexical search and deterministic reranking for fuzzy intent.

Hard filters:

- City.
- Date/time range.
- Price ceiling.
- Status.

Soft signals:

- Category.
- Vibes.
- Keywords.
- Tags.
- FTS relevance.

Example SQL shape:

```sql
SELECT
    e.id,
    e.title,
    e.description,
    e.city,
    e.venue_name,
    e.category,
    e.subcategory,
    e.start_at,
    e.end_at,
    e.min_price,
    e.max_price,
    e.currency,
    e.status,
    e.url,
    e.image_url,
    e.latitude,
    e.longitude,
    bm25(events_fts) AS bm25_score
FROM events e
JOIN events_fts ON events_fts.rowid = e.id
WHERE e.city = :city
  AND e.start_at >= :date_from
  AND e.start_at <= :date_to
  AND e.status IN ('onsale', 'unknown')
  AND (:max_price IS NULL OR e.min_price IS NULL OR e.min_price <= :max_price)
  AND events_fts MATCH :fts_query
ORDER BY bm25(events_fts)
LIMIT :limit;
```

The SQL builder only accepts `NormalizedQuery`, never raw LLM output.

## 8. Ranking

Raw FTS ordering is not the final recommendation order. Python reranks candidates deterministically.

Current MVP scoring formula:

```python
score = (
    0.50 * lexical_score +
    0.25 * temporal_score +
    0.15 * price_score +
    0.10 * tag_overlap_score
)
```

Where:

- `lexical_score`: normalized FTS/BM25 relevance.
- `temporal_score`: closer events to the requested time score higher.
- `price_score`: events fitting the budget score higher.
- `tag_overlap_score`: category/vibe/tag overlap boost.

The ranking engine is the actual recommender. The LLM does not choose winners from the full DB.

## 9. Database Schema

The MVP uses four normal tables plus one FTS5 virtual table.

Normal tables:

- `events`
- `raw_events`
- `chat_sessions`
- `chat_messages`

Search index:

- `events_fts`

SQLite row IDs should be incremental integers for the MVP. This keeps the schema simple and makes `events_fts.rowid = events.id` work correctly with SQLite FTS5.

### SQLite DDL

```sql
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
```

### FTS Sync Triggers

The trigger names are written out clearly instead of using short names like `events_ai`.

```sql
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
```

Because `events.id` is an integer primary key, it can be used directly as the FTS5 `rowid`.

## 10. Upsert Strategy

External-source identity is:

```text
(source, source_event_id)
```

This is the deduplication key for both `events` and `raw_events`.

For `events`, ingestion should:

- Insert a new row if the source event is new.
- Update normalized fields if the source event already exists.
- Always update `last_seen_at`.
- Preserve `id` across updates.

For `raw_events`, ingestion should:

- Insert a new row if the source event is new.
- Replace `payload_json` and `fetched_at` if the source event already exists.

## 11. Status And Image Fields

`status` stores event availability/state from the source, for example:

- `onsale`
- `scheduled`
- `offsale`
- `cancelled`
- `postponed`
- `rescheduled`
- `unknown`

It prevents the system from recommending cancelled or unavailable events.

`image_url` stores a display image from the event source. It is not needed for retrieval but is useful for cards, demos, and richer API responses.

## 12. Constraints And Guardrails

The system must preserve these boundaries:

- Recommendations come only from the local DB.
- The LLM does not invent events.
- The LLM does not write SQL.
- The LLM does not rank the whole DB by intuition.
- The LLM does not call Ticketmaster during chat.
- Chat history and retrieval state are separate concepts.
- `QuerySpec` and DB schema are separate contracts.
- The SQL builder accepts only normalized validated data.

## 13. Open Decisions

The following items still need to be locked before implementation:

- Final `QuerySpec` Pydantic model.
- Final `NormalizedQuery` Pydantic model.
- Allowed internal category ontology.
- Vibe/tag expansion rules.
- Date/time normalization rules for `tonight`, `tomorrow`, `this weekend`, and similar phrases.
- Exact FTS query escaping strategy.
- Exact scoring functions for each ranking component.
- Whether `POST /ingest` should support only city/date parameters or broader Ticketmaster filters.
- Project folder structure.
