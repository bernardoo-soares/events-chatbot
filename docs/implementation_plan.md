# Implementation Plan

## 1. Workflow

Implementation should proceed in small, reviewable sprints. Each sprint must leave the repo in a runnable or testable state.

The implementation order is:

```text
project scaffold
-> database/schema
-> ingestion
-> retrieval
-> LLM/Agno layer
-> FastAPI endpoints
-> end-to-end hardening
```

Each sprint has:

- Goal.
- Scope.
- Deliverables.
- Tests/checkpoint.
- Review decision.
- Sprint log file.

## Sprint Logging

At the end of each sprint, create a log file under:

```text
docs/logs/sprint_NUMBER.md
```

Use two digits for the number:

```text
docs/logs/sprint_00.md
docs/logs/sprint_01.md
docs/logs/sprint_02.md
```

Each sprint log must include:

- Sprint name.
- Date/time completed.
- Files created or changed.
- Summary of implemented behavior.
- Tests/checks run.
- Test results.
- Important decisions made during implementation.
- Known issues or follow-up items.
- Whether the sprint is ready for review.

Template:

```markdown
# Sprint NUMBER - Sprint Name

## Completed At

YYYY-MM-DD HH:MM timezone

## Files Changed

- path/to/file.py

## Summary

Short implementation summary.

## Tests And Checks

- `python -m compileall src tests`: pass/fail
- `python -m pytest -q`: pass/fail
- `ruff check .`: pass/fail/not configured

## Decisions

- Decision made and why.

## Known Issues

- Issue or `None`.

## Review Status

Ready for review / blocked.
```

## Sprint 0: Project Scaffold

### Goal

Create the basic repo structure and local development setup.

### Scope

- Create `pyproject.toml`.
- Create `src/event_chatbot/` package.
- Use the exact package import path `event_chatbot.main:app`.
- Create `tests/` structure.
- Create `.env.example`.
- Create `.gitignore`.
- Create `README.md` placeholder.
- Add minimal `main.py` FastAPI app with `/health`.

### Deliverables

- Package imports correctly.
- FastAPI app can start.
- `/health` returns status.

### Checkpoint

- `python -m compileall src`
- `python -m pytest -q`
- Manual: `uvicorn event_chatbot.main:app --reload`

### Review

Approve structure before adding business logic.

## Sprint 1: SQLite Schema And DB Layer

### Goal

Implement the database schema and connection/migration helpers.

### Scope

- Add `src/event_chatbot/db/schema.sql`.
- Add `db/connection.py` with `connect()` and `transaction()`.
- Add `db/migrations.py` with `initialize_database()`.
- Implement schema initialization from package `schema.sql`.
- Add tests for table creation and FTS availability.

### Deliverables

- SQLite DB can be initialized from code.
- `events_fts` is created.
- FTS triggers sync inserted/updated/deleted events.

### Checkpoint

- Unit/integration tests for schema creation.
- Integration test inserts event and verifies FTS match.

### Review

Validate schema before repository code is built on top of it.

## Sprint 2: Types And Repositories

### Goal

Add typed application objects and explicit DB repositories.

### Scope

- Add Pydantic types from `docs/technical_plan.md`:
  - `QuerySpec`
  - `HardFilters`
  - `NormalizedQuery`
  - `SearchRequest`
  - `Event`
  - `EventCandidate`
  - `EventUpsert`
  - `RawEventUpsert`
  - `IngestionRequest`
  - `IngestionSummary`
  - `UpsertSummary`
  - `SourcePayload`
  - `SourceEvent`
  - `ChatRequest`
  - `ChatResponse`
  - `ChatMessage`
  - `SessionState`
- Implement `EventRepository.upsert_many()`, `EventRepository.search_candidates()`, and `EventRepository.get_by_ids()`.
- Implement `RawEventRepository.upsert_many()`.
- Implement `ChatSessionRepository.get_or_create()`, `ChatSessionRepository.save_state()`, and `ChatSessionRepository.append_message()`.
- Add upsert logic by `(source, source_event_id)`.

### Deliverables

- Events can be inserted and updated.
- Raw payloads can be inserted and updated.
- Chat session state can be saved and loaded.

### Checkpoint

- Tests for event upsert preserving `id`.
- Tests for raw event upsert.
- Tests for chat session persistence.
- Verify no duplicate event rows for same source event.

### Review

Confirm repository methods are minimal and do not duplicate DB calls.

## Sprint 3: Ticketmaster Ingestion

### Goal

Fetch real events from Ticketmaster and store them locally.

### Scope

- Add `EventSourceProvider` protocol.
- Add `TicketmasterProvider`.
- Add `normalize_ticketmaster_event()`.
- Add `IngestionService.ingest()`.
- Add `POST /ingest` endpoint.
- CLI command is optional and should not block the sprint.

### Deliverables

- Ingestion can run with a real API key.
- Raw payloads are stored.
- Normalized event rows are stored.
- FTS index is populated.
- Ingestion returns a summary.

### Checkpoint

- Unit tests with fake Ticketmaster payloads.
- Integration test using fake provider.
- Manual smoke test with real `TICKETMASTER_API_KEY`.

### Review

Confirm stored event rows have enough data for retrieval: title, city, venue, date, category, status, URL, image.

## Sprint 4: QuerySpec, Normalization, And Retrieval

### Goal

Implement the deterministic retrieval engine.

### Scope

- Implement `QuerySpec`, `HardFilters`, `NormalizedQuery`, and `SearchRequest` as specified in `docs/technical_plan.md`.
- Implement session-state merge.
- Implement date/time normalization.
- Implement category/vibe soft signal mapping.
- Implement FTS query escaping.
- Implement SQL query builder.
- Implement ranking formula.
- Implement `RetrievalService.normalize()` and `RetrievalService.search()`.
- Add `GET /events/search`.

### Deliverables

- Deterministic search works without LLM.
- Search accepts natural-ish debug parameters.
- Ranking returns stable results.

### Checkpoint

- Unit tests for normalization.
- Unit tests for FTS escaping.
- Unit tests for ranking components.
- Integration test with seeded events.
- Manual search examples:
  - `jazz in Lisbon tonight`
  - `events under 30 euros`
  - `only sports`

### Review

This is the most important sprint. Do not wire Agno until retrieval quality is understandable through `/events/search`.

## Sprint 5: Agno LLM Layer

### Goal

Use Agno narrowly for intent extraction and grounded response rendering.

### Scope

- Add `IntentExtractor` protocol.
- Add `ResponseRenderer` protocol.
- Add fake implementations for tests.
- Add `AgnoIntentExtractor`.
- Add `AgnoResponseRenderer`.
- Add prompt/instruction templates.
- Ensure structured output returns `QuerySpec`.

### Deliverables

- LLM can convert user message to `QuerySpec`.
- LLM can render grounded rows into natural language.
- Tests do not require real LLM keys.

### Checkpoint

- Unit tests use fake LLM provider.
- Manual smoke test with real `OPENAI_API_KEY`.
- Validate LLM cannot bypass retrieval or invent events in the app flow.

### Review

Confirm Agno remains a thin conversational layer and does not own retrieval.

## Sprint 6: Chat Endpoint

### Goal

Implement the complete `/chat` workflow.

### Scope

- Add `ChatService.chat()`.
- Add `/chat` router.
- Load session state.
- Extract intent.
- Merge state.
- Retrieve and rank events.
- Save updated state and messages.
- Render grounded response.

### Deliverables

- `/chat` works with fake LLM in tests.
- `/chat` works manually with real LLM and seeded DB.
- Follow-up questions can reuse prior state.

### Checkpoint

- Integration test for first-turn chat.
- Integration test for follow-up query such as "what about tomorrow?"
- Integration test for empty results.

### Review

Confirm end-to-end behavior is grounded and readable.

## Sprint 7: Hardening And Delivery

### Goal

Prepare the challenge submission.

### Scope

- Complete README run instructions.
- Complete `.env.example`.
- Add AI usage note.
- Add sample commands.
- Add error handling.
- Add clear logging.
- Run final tests.
- Optional: add Codex log reference.

### Deliverables

- Fresh clone can run with documented steps.
- App can initialize DB.
- App can ingest events.
- App can search events.
- App can chat over grounded data.

### Checkpoint

- `python -m pytest -q`
- `python -m compileall src tests`
- Manual run:
  - initialize DB
  - ingest Lisbon events
  - call `/events/search`
  - call `/chat`

### Review

Final review before submission.

## Sprint 8: AgendaLX Lisbon Ingestion

### Goal

Add AgendaLX as a first-class Lisbon event provider while preserving the existing ingestion abstraction.

### Scope

- Add `AgendaLXProvider` implementing `EventSourceProvider`.
- Fetch `https://www.agendalx.pt/wp-json/agendalx/v1/events` with `per_page=100`.
- Paginate with `page=1`, `page=2`, `page=3`, etc.
- Stop when the response is empty, shorter than `per_page`, or the requested size is reached.
- Normalize AgendaLX payloads into `SourceEvent`.
- Use `source="agendalx"` and `source_event_id=str(id)`.
- Use fixed Lisbon metadata: `city="Lisbon"` and `timezone="Europe/Lisbon"`.
- Drop events that ended before today's Lisbon-local midnight.
- Keep long-running events when `LastDate` is today or later.
- Add `source` to `IngestionRequest` with default `"ticketmaster"`.
- Add a source-aware ingestion factory.
- Update `/ingest` to select the provider from the request body.

### Deliverables

- AgendaLX events can be ingested into the same `raw_events`, `events`, and `events_fts` tables.
- No DB schema change is required.
- Ticketmaster ingestion remains the default path.
- Lisbon DB coverage improves through AgendaLX.

### Checkpoint

- Unit tests for AgendaLX pagination.
- Unit tests for AgendaLX normalization.
- Unit tests for past-event filtering.
- Integration checks for the existing ingestion service.
- Manual smoke test with real AgendaLX API:
  - `source="agendalx"`
  - `city="Lisbon"`
  - `size=300`

### Review

Confirm AgendaLX behaves as a clean connector and does not add provider-specific logic to repositories or retrieval.

## Sprint 9: Web Chat UI

### Goal

Add a compelling browser-based conversational interface served by the existing FastAPI app.

### Scope

- Add a static web app under `src/event_chatbot/web/`.
- Serve `/` from FastAPI.
- Mount static assets under `/static`.
- Build a pink gradient launch page with glassmorphism chat UI.
- Wire the frontend to `POST /chat`.
- Persist browser session id in `localStorage`.
- Add a refresh/new-session button.
- Show a classical three-dot loading state with the text `I'm thinking`.
- Render assistant messages and top three structured event cards.
- Add quick prompt chips.
- Keep the frontend dependency-free and avoid a Node build step.

### Deliverables

- `http://127.0.0.1:8000` opens the web UI.
- Chat requests hit the existing backend.
- Event cards render from `results`, not from model-generated text.
- User can restart with a fresh session.

### Checkpoint

- Unit test for `/`.
- Unit test for `/static/app.js` and `/static/styles.css`.
- Manual browser smoke test.
- `python -m pytest -q`
- `python -m ruff check .`
- `python -m compileall src tests`

### Review

Confirm the UI gives a strong demo impression without changing backend contracts.

## 2. Senior Engineering Guardrails

Implementation should follow these rules throughout:

- Do not add abstractions without a concrete use.
- Use provider protocols only at external boundaries.
- Keep repositories focused on DB access.
- Keep services focused on workflow.
- Keep Pydantic models near typed application concepts.
- Do not let API routers contain business logic.
- Do not let LLM output touch SQL directly.
- Do not make external API calls in automated tests.
- Do not re-fetch event rows after retrieval unless needed.
- Keep all user-facing recommendations traceable to `events.id`.

## 3. Suggested First Coding Step

Start with Sprint 0 and Sprint 1.

Reason:

- The repo structure and DB schema are the foundation.
- Retrieval and ingestion both depend on the DB layer.
- It gives an early executable checkpoint before adding external providers or LLMs.

After Sprint 1, implementation can proceed safely into Ticketmaster ingestion and retrieval.
