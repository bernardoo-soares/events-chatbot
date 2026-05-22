# AGENTS.md

## Purpose

This repository is a grounded local event-discovery chatbot. The product promise is that
recommendations come from real event rows stored in SQLite, not from model imagination.

The main runtime flow is:

```text
Ticketmaster / AgendaLX ingestion
-> SQLite events + FTS5 + event embeddings
-> deterministic normalization and candidate retrieval
-> deterministic ranking with lexical, semantic, temporal, price, and tag signals
-> template-rendered grounded response
-> FastAPI API + static web UI
```

## Core Boundaries

- Do not let the LLM create event recommendations.
- Do not let the LLM write SQL.
- Do not call live event providers from `/chat`.
- Recommendations must be traceable to `events.id`.
- Hard filters stay deterministic: city, date window, status, price, explicit category-only.
- Semantic embeddings are soft ranking signals only. They must not bypass hard filters.
- Chat session state is explicit in `chat_sessions`; do not rely on hidden LLM memory.
- Tests must not require real OpenAI, Ticketmaster, or AgendaLX network calls.

## Run And Check

Common local commands:

```bash
python -m pip install -e .[dev]
python -m uvicorn event_chatbot.main:app --reload
python -m pytest -q
python -m compileall src tests
python -m ruff check .
```

The app import path is:

```text
event_chatbot.main:app
```

The default local/demo DB is:

```text
data/demo_events.db
```

Be careful with this file. It is a real SQLite database and can become large when embeddings are
backfilled. Do not reset or delete it unless explicitly asked.

## Environment

Settings are loaded from `.env` through `pydantic-settings`. Important variables:

```text
DATABASE_PATH
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_EMBEDDING_MODEL
SEMANTIC_RANKING_ENABLED
EMBEDDING_BATCH_SIZE
TICKETMASTER_API_KEY
AGENDALX_BASE_URL
DEFAULT_CITY
DEFAULT_TIMEZONE
INGEST_DEFAULT_DAYS
```

Never commit secrets. `.env.example` should contain placeholders and safe defaults only.

## Architecture Rules

- Keep routers thin. They should parse requests, use dependencies, call services, and return typed
  responses.
- Keep services as workflow orchestration.
- Keep repositories focused on SQLite access.
- Keep providers focused on external APIs or protocol boundaries.
- Keep retrieval logic deterministic and testable.
- Keep Pydantic business contracts in `types/`.
- Prefer small explicit modules over deep framework abstractions.
- Use parameterized SQL only.
- Do not add a new dependency unless it clearly improves this challenge app.
- When adding ranking behavior, add focused tests that prove the ranking effect.

## Current Retrieval Design

Retrieval is hybrid:

```text
NormalizedQuery
-> SQLite hard filters and optional FTS candidates
-> optional OpenAI embedding semantic scoring over candidate event embeddings
-> deterministic ranking
-> duplicate-title suppression
-> bounded API result list
```

Ranking currently includes:

```text
lexical_score
semantic_score
temporal_score
price_score
tag_overlap_score
```

Missing embeddings or embedding API failure should degrade to neutral semantic scores and keep
retrieval working.

## Editing Guidance

- Preserve existing user changes in the working tree.
- Use `apply_patch` for manual edits.
- Keep comments sparse and useful.
- Default to ASCII in files unless the existing file clearly requires Unicode.
- Avoid unrelated refactors.
- Do not run destructive git commands.

## Documentation

The most useful docs are:

```text
README.md
docs/architecture.md
docs/technical_plan.md
docs/implementation_plan.md
docs/logs/
```

Update docs only when behavior or setup changes enough that a future developer would be misled.
