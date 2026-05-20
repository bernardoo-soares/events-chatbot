# Technical Plan

## 1. Purpose

This document translates the approved architecture into a concrete repository and code design.

The goal is to build a small, readable, testable event-discovery chatbot API without overengineering it. The implementation should keep the LLM layer narrow, the retrieval layer deterministic, and the database interactions explicit.

## 2. External References Checked

The plan follows current public documentation patterns from:

- FastAPI larger-app structure with `APIRouter`: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI SQL database guidance: https://fastapi.tiangolo.com/tutorial/sql-databases/
- Agno framework/runtime positioning: https://docs.agno.com/
- Agno structured output for agents: https://docs.agno.com/input-output/structured-output/agent
- Agno AgentOS overview: https://docs.agno.com/agent-os/overview
- uv project management: https://docs.astral.sh/uv/concepts/projects/

## 3. Design Principles

- Keep the app easy to read before optimizing abstractions.
- Use dependency injection at API boundaries, not everywhere.
- Use provider interfaces for external services.
- Keep DB writes transactional and explicit.
- Keep retrieval deterministic and testable.
- Avoid redundant DB calls by passing loaded rows through the workflow.
- Keep LLM output separate from DB schema.
- Keep ingestion separate from chat.
- Prefer simple Python modules over deep framework-style layering.
- Use tests as checkpoint gates for each implementation sprint.
- Every public service/repository method should have a single clear responsibility.
- Every module should be understandable without reading the whole project.
- Any behavior that affects retrieval quality must be specified and tested.
- If implementation discovers ambiguity, update this plan before coding around it.

## 4. Proposed Repository Structure

```text
.
|-- docs/
|   |-- architecture.md
|   |-- technical_plan.md
|   `-- implementation_plan.md
|-- src/
|   `-- event_chatbot/
|       |-- __init__.py
|       |-- main.py
|       |-- api/
|       |   |-- __init__.py
|       |   |-- dependencies.py
|       |   `-- routers/
|       |       |-- __init__.py
|       |       |-- chat.py
|       |       |-- events.py
|       |       |-- health.py
|       |       `-- ingest.py
|       |-- core/
|       |   |-- __init__.py
|       |   |-- config.py
|       |   |-- logging.py
|       |   `-- time.py
|       |-- db/
|       |   |-- __init__.py
|       |   |-- connection.py
|       |   |-- migrations.py
|       |   `-- schema.sql
|       |-- types/
|       |   |-- __init__.py
|       |   |-- events.py
|       |   |-- ingestion.py
|       |   |-- query.py
|       |   `-- chat.py
|       |-- providers/
|       |   |-- __init__.py
|       |   |-- event_source.py
|       |   |-- llm.py
|       |   |-- ticketmaster.py
|       |   `-- agno_llm.py
|       |-- repositories/
|       |   |-- __init__.py
|       |   |-- events.py
|       |   |-- raw_events.py
|       |   `-- chat_sessions.py
|       |-- services/
|       |   |-- __init__.py
|       |   |-- chat_service.py
|       |   `-- ingestion_service.py
|       `-- retrieval/
|           |-- __init__.py
|           |-- normalization.py
|           |-- fts.py
|           |-- query_builder.py
|           |-- ranking.py
|           `-- service.py
|-- tests/
|   |-- conftest.py
|   |-- unit/
|   |   |-- test_normalization.py
|   |   |-- test_ranking.py
|   |   |-- test_query_builder.py
|   |   `-- test_ticketmaster_normalization.py
|   `-- integration/
|       |-- test_db_schema.py
|       |-- test_ingestion_flow.py
|       |-- test_retrieval_flow.py
|       `-- test_chat_api.py
|-- .env.example
|-- .gitignore
|-- pyproject.toml
`-- README.md
```

## 5. Package And Runtime

Use `uv` with a `pyproject.toml`.

Expected runtime dependencies:

- `fastapi`
- `uvicorn`
- `pydantic`
- `pydantic-settings`
- `httpx`
- `agno`
- `openai`

Expected test/dev dependencies:

- `pytest`
- `pytest-cov`
- `ruff`
- `mypy`

Use Python `3.11+`.

Do not add a frontend in the MVP. The OpenAPI docs and JSON responses are enough.

### `pyproject.toml` Expectations

The project should use a `src` layout:

```toml
[project]
name = "event-chatbot"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

The FastAPI app import path should be:

```text
event_chatbot.main:app
```

The local run command should be:

```text
uvicorn event_chatbot.main:app --reload
```

## 6. Data Access Strategy

Use SQLite directly through a small DB connection layer.

Reasoning:

- The schema includes FTS5 virtual tables and triggers, which are easiest to define in raw SQL.
- The MVP does not need ORM complexity.
- Repository methods can stay small and explicit.
- Tests can use temporary SQLite databases.

`db/schema.sql` contains the exact DDL from `docs/architecture.md`.

`db/connection.py` responsibilities:

- Create SQLite connections.
- Set `row_factory = sqlite3.Row`.
- Enable `PRAGMA foreign_keys = ON`.
- Provide transaction helpers.

`db/migrations.py` responsibilities:

- Apply `schema.sql`.
- Optionally rebuild FTS index if needed.

No query should be built through string interpolation from user input. SQL values always use parameters.

### DB Connection Contract

`db/connection.py` should expose:

```python
def connect(database_path: str) -> sqlite3.Connection:
    ...

@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    ...
```

Connection setup must:

- Set `conn.row_factory = sqlite3.Row`.
- Execute `PRAGMA foreign_keys = ON`.
- Use normal synchronous SQLite calls.

Transaction behavior:

- Commit on success.
- Roll back on exception.
- Never swallow exceptions.

### Migration Contract

`db/migrations.py` should expose:

```python
def initialize_database(conn: sqlite3.Connection) -> None:
    ...
```

It must:

- Read `db/schema.sql` from the package.
- Execute the full schema script.
- Be safe to call multiple times.
- Not delete existing data.

## 7. Types

The `types/` folder contains the core typed data objects of the application.

These models describe events, ingestion, user search intent, normalized queries, chat sessions, and ranked recommendations. They are not tied to FastAPI, SQLite, Ticketmaster, or Agno. They are the stable internal vocabulary of the app.

This separation keeps external concerns from leaking everywhere:

- API request/response details stay in `api/`.
- SQLite access stays in `repositories/` and `db/`.
- Ticketmaster and Agno stay in `providers/`.
- Typed business objects stay in `types/`.

Types are Pydantic models used inside the app. They are not DB ORM models.

### `types/query.py`

Defines:

- `QuerySpec`
- `NormalizedQuery`
- `HardFilters`
- `SearchRequest`
- `RankedEvent`

`QuerySpec` is produced by the LLM.

`NormalizedQuery` is produced by deterministic Python and is the only input accepted by the SQL query builder.

Expected model shapes:

```python
AllowedTimeOfDay = Literal["morning", "afternoon", "evening", "night"]

class QuerySpec(BaseModel):
    city: str | None = None
    raw_category_text: str | None = None
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    vibes: list[str] = Field(default_factory=list)
    date_text: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    time_of_day: AllowedTimeOfDay | None = None
    max_price: float | None = None
    radius_km: float | None = None
    hard_category_only: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None

class HardFilters(BaseModel):
    city: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    max_price: float | None = None
    statuses: list[str] = Field(default_factory=lambda: ["onsale", "unknown"])
    hard_category_filters: list[str] = Field(default_factory=list)

class NormalizedQuery(BaseModel):
    hard_filters: HardFilters
    city_slug: str | None = None
    category_boosts: list[str] = Field(default_factory=list)
    vibe_tags: list[str] = Field(default_factory=list)
    fts_terms: list[str] = Field(default_factory=list)
    limit: int = 20
    candidate_limit: int = 200
    used_fts: bool = False

class SearchRequest(BaseModel):
    city: str | None = None
    q: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    max_price: float | None = None
    limit: int = 20
```

Implementation rules:

- Do not pass `QuerySpec` directly to SQL.
- `hard_category_only=True` is set only when the user uses explicit wording such as "only sports", "just concerts", or "no other categories".
- `limit` is the number returned to the API response.
- `candidate_limit` is the max number fetched before reranking.

### `types/events.py`

Defines:

- `Event`
- `EventCandidate`
- `EventUpsert`
- `RawEventUpsert`

Use DB field names where practical to reduce translation overhead.

Expected model notes:

- `Event.id` is `int`.
- `start_at`, `end_at`, `ingested_at`, `last_seen_at`, and `fetched_at` are timezone-aware `datetime` objects in Python.
- Datetimes are stored as ISO-8601 strings in SQLite.
- `min_price` and `max_price` are `float | None`.
- `status` defaults to `"unknown"` if missing from source data.

### `types/ingestion.py`

Defines:

- `IngestionRequest`
- `IngestionSummary`
- `UpsertSummary`
- `SourcePayload`
- `SourceEvent`

`SourcePayload` is the source-identified raw payload returned by an event provider.

`SourceEvent` is the normalized intermediate object after converting a source payload but before DB upsert.

`IngestionRequest` should include:

```python
class IngestionRequest(BaseModel):
    city: str
    date_from: date | None = None
    date_to: date | None = None
    size: int = 200
```

`IngestionSummary` should include:

```python
class IngestionSummary(BaseModel):
    source: str
    fetched: int
    inserted: int
    updated: int
    errors: int

class UpsertSummary(BaseModel):
    inserted: int
    updated: int

class SourcePayload(BaseModel):
    source: str
    source_event_id: str
    payload: dict[str, Any]
```

### `types/chat.py`

Defines:

- `ChatRequest`
- `ChatResponse`
- `ChatMessage`
- `SessionState`

`SessionState.current_query` stores the latest merged `QuerySpec`-like state as JSON. It should not store arbitrary LLM conversation history. `chat_messages` stores the message audit trail.

## 8. Provider Abstractions

Use `typing.Protocol` for provider interfaces. Protocols are lighter than abstract base classes and fit Python dependency injection well. Use `abc.ABC` only if shared implementation or inherited behavior is useful.

### Event Source Provider

`providers/event_source.py`:

```python
class EventSourceProvider(Protocol):
    def fetch_events(self, request: IngestionRequest) -> list[SourcePayload]:
        ...
```

Ticketmaster implementation:

```text
TicketmasterProvider
-> calls Ticketmaster Discovery API
-> handles pagination
-> returns raw source payloads
```

The normalizer is separate:

```text
Ticketmaster payload
-> TicketmasterEventNormalizer
-> SourceEvent
```

This makes it possible to add Eventbrite or PredictHQ later without changing ingestion orchestration.

### Ticketmaster Provider Contract

`providers/ticketmaster.py` should contain:

```python
class TicketmasterProvider:
    source = "ticketmaster"

    def __init__(self, api_key: str, base_url: str, client: httpx.Client | None = None):
        ...

    def fetch_events(self, request: IngestionRequest) -> list[SourcePayload]:
        ...
```

Required behavior:

- Query Ticketmaster Discovery API event endpoint.
- Use `apikey` authentication.
- Use city/date/size parameters from `IngestionRequest`.
- Handle pagination until `size` records or source exhaustion.
- Extract Ticketmaster event id into `SourcePayload.source_event_id`.
- Raise a clear provider error for non-2xx responses.
- Never write to the database directly.

Ticketmaster normalization should be a separate function or class:

```python
def normalize_ticketmaster_event(payload: SourcePayload, fetched_at: datetime) -> SourceEvent:
    ...
```

Required fields to extract when available:

- `source_event_id`
- `title`
- `description`
- `city`
- `venue_name`
- `category`
- `subcategory`
- `start_at`
- `end_at`
- `timezone`
- `min_price`
- `max_price`
- `currency`
- `status`
- `url`
- `image_url`
- `latitude`
- `longitude`

If optional source fields are missing, return `None` or `"unknown"` according to the domain model. Do not fail normalization only because optional data is missing.

### LLM Provider

`providers/llm.py`:

```python
class IntentExtractor(Protocol):
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        ...

class ResponseRenderer(Protocol):
    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        ...
```

Agno implementation:

```text
AgnoIntentExtractor
AgnoResponseRenderer
```

Possible future implementations:

- `OpenAIIntentExtractor`
- `VertexIntentExtractor`
- `FakeIntentExtractor` for tests

The app depends on the protocol, not the concrete provider.

### Agno Provider Contract

`providers/agno_llm.py` should contain:

```python
class AgnoIntentExtractor:
    def extract_intent(self, message: str, state: SessionState | None) -> QuerySpec:
        ...

class AgnoResponseRenderer:
    def render_response(self, query: NormalizedQuery, events: list[RankedEvent]) -> str:
        ...
```

Intent extraction instructions must include:

- Return only fields in `QuerySpec`.
- Do not write SQL.
- Do not invent event data.
- Use categories as suggestions, not final hard filters.
- Set `needs_clarification=True` only when retrieval cannot proceed safely, for example missing city and no default city configured.

Response rendering instructions must include:

- Use only supplied event rows.
- Do not add venues, prices, dates, or URLs not present in rows.
- If results are empty, say no matching events were found and suggest changing filters.
- Keep the answer concise.

Tests should use fake provider implementations, not Agno.

## 9. Repositories

Repositories own database access. Services own workflow.

### `EventRepository`

Responsibilities:

- Upsert normalized events by `(source, source_event_id)`.
- Search event candidates from a `NormalizedQuery`.
- Fetch events by ids when needed.

Important rule: retrieval should perform one candidate query and pass candidate rows into ranking. Avoid fetching the same event rows again after ranking unless required.

Required methods:

```python
class EventRepository:
    def upsert_many(self, events: list[SourceEvent], now: datetime) -> UpsertSummary:
        ...

    def search_candidates(self, query: NormalizedQuery) -> list[EventCandidate]:
        ...

    def get_by_ids(self, ids: list[int]) -> list[Event]:
        ...
```

Upsert behavior:

- Match existing rows by `(source, source_event_id)`.
- Insert when no existing row is found.
- Update when existing row is found.
- Preserve `events.id` on update.
- Set `ingested_at` only on insert.
- Set `last_seen_at` on insert and update.

`search_candidates()` behavior:

- Build SQL from `NormalizedQuery`.
- Apply hard filters in SQL.
- Apply FTS `MATCH` only when `query.used_fts` is true.
- Return at most `query.candidate_limit` rows.
- Include `bm25_score` when FTS is used.
- Return enough fields for ranking and response rendering so no second fetch is needed.

### `RawEventRepository`

Responsibilities:

- Upsert raw payloads by `(source, source_event_id)`.

Required methods:

```python
class RawEventRepository:
    def upsert_many(self, payloads: list[SourcePayload], fetched_at: datetime) -> UpsertSummary:
        ...
```

Raw payloads are stored as compact JSON strings.

### `ChatSessionRepository`

Responsibilities:

- Create/update session state.
- Append chat messages.
- Store `current_query_json`.
- Store `last_result_ids_json`.

Session state is not delegated to LLM memory.

Required methods:

```python
class ChatSessionRepository:
    def get_or_create(self, session_id: str, now: datetime) -> SessionState:
        ...

    def save_state(self, session_id: str, state: SessionState, now: datetime) -> None:
        ...

    def append_message(self, session_id: str, role: str, message_text: str, now: datetime) -> None:
        ...
```

## 10. Services

### `IngestionService`

Workflow:

```text
IngestionRequest
-> EventSourceProvider.fetch_events()
-> RawEventRepository.upsert_many()
-> source normalizer
-> EventRepository.upsert_many()
-> return IngestionSummary
```

This service should run in one explicit transaction per ingestion batch where practical.

Required method:

```python
class IngestionService:
    def ingest(self, request: IngestionRequest) -> IngestionSummary:
        ...
```

Error handling:

- Provider failure should return/raise a clear application error.
- A malformed individual event should increment `errors` and not stop the whole batch unless every event fails.
- Raw payloads should still be stored when possible, even if normalization fails for some records.

### `RetrievalService`

Workflow:

```text
QuerySpec
-> NormalizedQuery
-> EventRepository.search_candidates()
-> rank_candidates()
-> list[RankedEvent]
```

The service should expose a deterministic method usable by both:

- `GET /events/search`
- `POST /chat`

Required methods:

```python
class RetrievalService:
    def normalize(self, spec: QuerySpec, previous: SessionState | None = None) -> NormalizedQuery:
        ...

    def search(self, query: NormalizedQuery) -> list[RankedEvent]:
        ...
```

### `ChatService`

Workflow:

```text
ChatRequest
-> load SessionState
-> IntentExtractor.extract_intent()
-> merge prior state
-> RetrievalService.search()
-> ChatSessionRepository.save_state()
-> ResponseRenderer.render_response()
-> ChatSessionRepository.append_messages()
-> ChatResponse
```

The chat service owns orchestration. Agno owns only intent extraction and final wording.

Required method:

```python
class ChatService:
    def chat(self, request: ChatRequest) -> ChatResponse:
        ...
```

If `QuerySpec.needs_clarification` is true, `ChatService` should return the clarification question without running retrieval.

## 11. Retrieval Technical Specification

### Hard Filters

Hard filters exclude rows before ranking.

Use hard filters for:

- City.
- Date/time range.
- Status.
- Price ceiling.
- Explicit category-only requests.

SQL hard-filter behavior:

- If `city` is present, filter `events.city = :city`.
- If `date_from` is present, filter `events.start_at >= :date_from`.
- If `date_to` is present, filter `events.start_at <= :date_to`.
- If `max_price` is present, filter `events.min_price IS NULL OR events.min_price <= :max_price`.
- Always filter status to configured active statuses unless debug endpoint explicitly overrides this.
- If `hard_category_filters` is non-empty, filter category or subcategory against those values.

### Soft Signals

Soft signals affect score but should not automatically exclude rows.

Use soft signals for:

- Category suggestions.
- Vibes.
- Keywords.
- FTS relevance.
- Tag overlap.

Soft signals must not remove candidates by themselves. They influence `fts_terms`, `category_boosts`, `vibe_tags`, and ranking.

### Normalization Rules

`retrieval/normalization.py` owns deterministic normalization.

City:

- Trim whitespace.
- Preserve display city for SQL.
- Create `city_slug` by lowercasing and replacing spaces with hyphens.
- For MVP, no geocoding.

Dates:

- If `QuerySpec.date_from/date_to` are present, parse them as dates or datetimes in `DEFAULT_TIMEZONE`.
- If `date_text == "tonight"`, set `date_from` to today at `18:00` and `date_to` to today at `23:59:59`.
- If `date_text == "tomorrow"`, set full-day tomorrow boundaries.
- If `date_text == "this weekend"`, set Saturday `00:00` through Sunday `23:59:59` for the upcoming weekend.
- If no date is present, default to now through `now + INGEST_DEFAULT_DAYS`.

Time of day:

- `morning`: `06:00` to `11:59:59`
- `afternoon`: `12:00` to `17:59:59`
- `evening`: `18:00` to `22:59:59`
- `night`: `21:00` to `02:00` next day

Categories:

- Allowed MVP categories are `music`, `sports`, `arts`, `theatre`, `family`, `food_drink`, `nightlife`, `community`, `business`, `other`.
- LLM category suggestions outside this list are moved into `fts_terms`.
- Category suggestions inside this list become `category_boosts`.
- They become `hard_category_filters` only when `QuerySpec.hard_category_only` is true.

Vibes:

- `chill` expands to `["chill", "casual", "relaxed"]`.
- `romantic` expands to `["romantic", "date night", "intimate"]`.
- `family-friendly` expands to `["family", "kids", "children"]`.
- `party` expands to `["party", "dj", "nightlife"]`.
- Unknown vibes are preserved as FTS terms.

Keywords:

- Keep user keywords as FTS terms after trimming.
- Drop empty strings.
- Deduplicate case-insensitively while preserving first spelling.

### FTS Query

`retrieval/fts.py` owns:

- FTS token escaping.
- Phrase handling.
- Empty-query fallback.
- `OR` query construction.

If no useful FTS terms exist, the query builder should still support date/city/status search without `MATCH`, then ranking should rely more on temporal and price scores.

FTS construction rules:

- Escape double quotes in terms.
- Terms with spaces become quoted phrases.
- Single-word terms remain unquoted unless they contain FTS syntax characters.
- Join terms with `OR`.
- Limit to the first 12 unique terms to avoid noisy queries.
- If terms are empty, set `used_fts=False` and do not include `events_fts MATCH` in SQL.

Example:

```python
["jazz", "live music", "drinks"]
```

becomes:

```text
jazz OR "live music" OR drinks
```

### Ranking

`retrieval/ranking.py` implements:

```python
score = (
    0.50 * lexical_score +
    0.25 * temporal_score +
    0.15 * price_score +
    0.10 * tag_overlap_score
)
```

All component scores must be floats in the range `0.0 <= score <= 1.0`.

The final score must be deterministic for the same candidate rows and `NormalizedQuery`.

### Lexical Score

Input:

- SQLite `bm25(events_fts)` value for each candidate.

SQLite FTS5 `bm25()` returns lower values for better matches. The ranking layer should convert this into a higher-is-better score.

For a candidate set:

```python
best = min(bm25_values)
worst = max(bm25_values)

if worst == best:
    lexical_score = 1.0
else:
    lexical_score = 1.0 - ((candidate_bm25 - best) / (worst - best))
```

If no FTS query was used, set:

```python
lexical_score = 0.5
```

Rationale: a neutral lexical score avoids unfairly zeroing valid date/city searches that do not include keywords.

### Temporal Score

Input:

- `event.start_at`
- `NormalizedQuery.hard_filters.date_from`
- `NormalizedQuery.hard_filters.date_to`
- current time from injected clock

If the query has a date range, score events closer to the preferred window start higher:

```python
window_start = query.date_from or now
delta_hours = abs((event.start_at - window_start).total_seconds()) / 3600
temporal_score = max(0.0, 1.0 - (delta_hours / 168.0))
```

This gives full score to events at the requested start and decays to `0.0` after one week.

If the query has no date range, score soon upcoming events higher:

```python
delta_hours = max(0.0, (event.start_at - now).total_seconds() / 3600)
temporal_score = max(0.0, 1.0 - (delta_hours / 720.0))
```

This decays to `0.0` after 30 days.

Past events must receive:

```python
temporal_score = 0.0
```

and should normally be excluded by SQL unless explicitly requested.

### Price Score

Input:

- `event.min_price`
- `event.max_price`
- `NormalizedQuery.hard_filters.max_price`

If the user did not specify a max price:

```python
price_score = 0.5
```

If the event has no price data:

```python
price_score = 0.6
```

Rationale: unknown price should not be excluded, but should not beat a known good price only because it is missing data.

If `event.min_price <= max_price`:

```python
price_score = 1.0
```

If `event.min_price > max_price`, the event should normally be excluded by SQL. If it reaches ranking because the SQL query is intentionally permissive, apply a soft penalty:

```python
over_budget_ratio = (event.min_price - max_price) / max_price
price_score = max(0.0, 1.0 - over_budget_ratio)
```

Examples:

- User max price `30`, event min price `30`: `1.0`
- User max price `30`, event min price `45`: `0.5`
- User max price `30`, event min price `60`: `0.0`

### Tag Overlap Score

Input:

- `NormalizedQuery.category_boosts`
- `NormalizedQuery.vibe_tags`
- `NormalizedQuery.fts_terms`
- event `category`
- event `subcategory`
- event searchable text fields

Build two sets:

```python
query_terms = normalized lower-case set from category_boosts + vibe_tags
event_terms = normalized lower-case set from event.category + event.subcategory
```

Then:

```python
if not query_terms:
    tag_overlap_score = 0.5
else:
    tag_overlap_score = len(query_terms & event_terms) / len(query_terms)
```

For MVP, do not infer hidden tags from the event description in this component. Text relevance is already handled by FTS. The tag overlap score should only use structured category/subcategory fields and deterministic normalized query boosts.

### Ranking Tie-Breakers

If two events have the same final score, sort deterministically by:

1. Earlier `start_at`.
2. Lower `min_price`, with unknown price after known price.
3. Lower `id`.

### Required Ranking Tests

Each component must be separately testable.

Required tests:

- BM25 values are converted from lower-is-better to higher-is-better.
- Empty FTS query gives neutral lexical score.
- Events closer to requested date score higher.
- Past events score `0.0` temporally.
- Known under-budget price beats unknown price.
- Unknown price beats clearly over-budget price.
- Category/vibe overlap boosts matching categories.
- Tie-breakers are stable.

## 12. API Technical Specification

### `POST /ingest`

Request:

```json
{
  "city": "Lisbon",
  "date_from": "2026-05-19",
  "date_to": "2026-06-19",
  "size": 200
}
```

Response:

```json
{
  "source": "ticketmaster",
  "fetched": 120,
  "inserted": 80,
  "updated": 40,
  "errors": 0
}
```

### `GET /events/search`

Purpose: deterministic retrieval debugging without LLM.

Query parameters:

- `city`
- `q`
- `date_from`
- `date_to`
- `max_price`
- `limit`

### `POST /chat`

Request:

```json
{
  "session_id": "abc-123",
  "message": "I want live jazz in Lisbon tonight under 30 euros"
}
```

Response:

```json
{
  "session_id": "abc-123",
  "assistant_message": "...",
  "applied_filters": {},
  "results": []
}
```

## 13. Configuration

Use `pydantic-settings`.

Settings:

- `APP_ENV`
- `DATABASE_PATH`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TICKETMASTER_API_KEY`
- `TICKETMASTER_BASE_URL`
- `DEFAULT_CITY`
- `DEFAULT_TIMEZONE`
- `INGEST_DEFAULT_DAYS`

`.env.example` should include placeholders only.

## 14. Testing Strategy

Testing is part of the implementation workflow, not an afterthought.

Unit tests:

- Query normalization.
- FTS query escaping.
- Ranking components.
- Ticketmaster payload normalization.
- Query builder parameter generation.

Integration tests:

- Schema creation.
- Event upsert.
- FTS sync triggers.
- Retrieval on seeded data.
- `/events/search`.
- `/chat` with fake LLM provider.

No integration test should require real OpenAI or Ticketmaster credentials. External providers are replaced with fakes.

Manual smoke tests:

- Run ingestion with a real Ticketmaster key.
- Run deterministic search.
- Run chat query with a real LLM key.

## 15. Quality Gates

Before considering a sprint complete:

- `python -m pytest -q` passes.
- `python -m compileall src tests` passes.
- `ruff check .` passes once tooling is configured.
- No external API call is required in automated tests.
- No LLM output is trusted before Pydantic validation and deterministic normalization.

## 16. Non-Goals For MVP

- No frontend UI.
- No background worker.
- No vector database.
- No MCP server.
- No multi-source ingestion beyond Ticketmaster.
- No advanced auth.
- No production scheduler.
- No complex migration framework unless schema changes become frequent.
