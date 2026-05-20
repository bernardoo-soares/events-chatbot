# Event Chatbot

Grounded local event-discovery chatbot API built with FastAPI, SQLite FTS5, Ticketmaster ingestion, and Agno-based LLM orchestration.

The LLM does not invent recommendations. Event recommendations come from the local SQLite database.

## Architecture

```text
Ticketmaster Discovery API
-> ETL ingestion
-> SQLite events database + FTS5 index
-> deterministic retrieval and ranking
-> Agno intent extraction and grounded response rendering
-> FastAPI API response
```

Core docs:

- `docs/architecture.md`
- `docs/technical_plan.md`
- `docs/implementation_plan.md`
- `docs/logs/`

## Requirements

- Python 3.11+
- Ticketmaster API key for ingestion
- OpenAI API key for chat through Agno

## Setup

```bash
python -m pip install -e .[dev]
```

Create a `.env` file based on `.env.example`:

```env
APP_ENV=local
DATABASE_PATH=data/events.sqlite
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o-mini
TICKETMASTER_API_KEY=your-ticketmaster-key
TICKETMASTER_BASE_URL=https://app.ticketmaster.com/discovery/v2
DEFAULT_CITY=Lisbon
DEFAULT_TIMEZONE=Europe/Lisbon
INGEST_DEFAULT_DAYS=30
```

## Run

```bash
uvicorn event_chatbot.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Ingest Events

```bash
curl -X POST http://127.0.0.1:8000/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"city\":\"Lisbon\",\"size\":50}"
```

## Deterministic Search

```bash
curl "http://127.0.0.1:8000/events/search?city=Lisbon&q=jazz&limit=5"
```

## Chat

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo\",\"message\":\"I want live jazz in Lisbon tonight under 30 euros\"}"
```

## Tests

```bash
python -m compileall src tests
python -m pytest -q
python -m ruff check .
```

Current automated tests use fake providers and do not require real OpenAI or Ticketmaster credentials.

## Important Boundaries

- No live Ticketmaster calls during chat.
- No LLM-generated SQL.
- No LLM-created event recommendations.
- Retrieval state is stored explicitly in `chat_sessions`.
- `events` and `events_fts` are the source of grounded recommendations.

