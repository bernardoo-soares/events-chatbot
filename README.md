# Event Chatbot

Grounded local event-discovery chatbot API built with FastAPI, SQLite FTS5, Ticketmaster/AgendaLX ingestion, and Agno-based LLM orchestration.

The LLM does not invent recommendations. Event recommendations come from the local SQLite database.

## Architecture

```text
Ticketmaster Discovery API / AgendaLX API
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
- AgendaLX ingestion does not require an API key
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
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
SEMANTIC_RANKING_ENABLED=true
EMBEDDING_BATCH_SIZE=100
TICKETMASTER_API_KEY=your-ticketmaster-key
TICKETMASTER_BASE_URL=https://app.ticketmaster.com/discovery/v2
AGENDALX_BASE_URL=https://www.agendalx.pt/wp-json/agendalx/v1
AGENDALX_PER_PAGE=100
DEFAULT_CITY=Lisbon
DEFAULT_TIMEZONE=Europe/Lisbon
INGEST_DEFAULT_DAYS=30
```

## Semantic Ranking

Semantic ranking uses OpenAI embeddings over stored event rows. Apply/backfill embeddings after
ingesting or changing the demo database:

```bash
curl -X POST http://127.0.0.1:8000/embeddings/backfill ^
  -H "Content-Type: application/json" ^
  -d "{\"limit\":1200}"
```

Retrieval still uses deterministic city/date/status/price filters first. Embeddings only influence
the final ranking score.

## Run

```bash
uvicorn event_chatbot.main:app --reload
```

Web app:

```text
http://127.0.0.1:8000
```

## Railway Deployment

The repo includes a populated demo database at:

```text
data/demo_events.db
```

Railway start command is defined in `Procfile`:

```text
web: uvicorn event_chatbot.main:app --host 0.0.0.0 --port $PORT
```

Set these Railway environment variables:

```env
APP_ENV=production
DATABASE_PATH=data/demo_events.db
OPEN_AI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
SEMANTIC_RANKING_ENABLED=true
EMBEDDING_BATCH_SIZE=100
TICKET_MASTER_CONSUMER_KEY=your-ticketmaster-key
TICKETMASTER_BASE_URL=https://app.ticketmaster.com/discovery/v2
AGENDALX_BASE_URL=https://www.agendalx.pt/wp-json/agendalx/v1
AGENDALX_PER_PAGE=100
DEFAULT_CITY=Lisbon
DEFAULT_TIMEZONE=Europe/Lisbon
INGEST_DEFAULT_DAYS=30
```

The deployed demo can chat and search using the committed DB immediately. New ingestion is optional.

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Ingest Events

```bash
curl -X POST http://127.0.0.1:8000/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"source\":\"ticketmaster\",\"city\":\"Lisbon\",\"size\":50}"
```

AgendaLX Lisbon ingestion:

```bash
curl -X POST http://127.0.0.1:8000/ingest ^
  -H "Content-Type: application/json" ^
  -d "{\"source\":\"agendalx\",\"city\":\"Lisbon\",\"size\":300}"
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

Current automated tests use fake providers and do not require real OpenAI, Ticketmaster, or AgendaLX network calls.

## Important Boundaries

- No live provider calls during chat.
- No LLM-generated SQL.
- No LLM-created event recommendations.
- Retrieval state is stored explicitly in `chat_sessions`.
- `events` and `events_fts` are the source of grounded recommendations.
