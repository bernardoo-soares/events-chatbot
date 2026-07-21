# Grounded Event Chatbot

[![CI](https://github.com/bernardoo-soares/events-chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/bernardoo-soares/events-chatbot/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688.svg)](https://fastapi.tiangolo.com/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Grounded local event-discovery chatbot API built with FastAPI, SQLite FTS5, Ticketmaster/AgendaLX ingestion, and Agno-based LLM orchestration.

The LLM does not invent recommendations. Event recommendations come from real rows in the local SQLite database, then deterministic retrieval, semantic ranking, and duplicate suppression decide what is shown.

## Technical Highlights

- FastAPI backend with typed request/response contracts.
- SQLite event store with FTS5 search and explicit chat session state.
- Hybrid retrieval with deterministic hard filters plus optional semantic ranking.
- Ticketmaster and AgendaLX ingestion paths normalized into one event schema.
- Template-rendered responses grounded in `events.id`.
- Static web UI backed by structured API results.
- Tests use fake providers and do not require live OpenAI, Ticketmaster, or AgendaLX calls.

## Live Demo

Use the deployed app here:

```text
https://web-production-53075.up.railway.app/
```

Try prompts like:

```text
What can I do in Lisbon this weekend?
Give me a place to drink wine today in Lisboa.
Comedy in Madrid under 25 euros.
I want something relaxed in Lisbon tomorrow.
```

Portuguese city aliases such as `Lisboa` are normalized to the database city name `Lisbon` before search.

## Architecture

```text
Ticketmaster Discovery API / AgendaLX API
-> ETL ingestion
-> SQLite events database + FTS5 index
-> event embeddings
-> Agno request-intent + QuerySpec extraction
-> deterministic filters, retrieval, semantic ranking, and dedupe
-> FastAPI response + frontend cards
```

The LLM extracts structured intent only. It does not write SQL, choose final recommendations, or create event details.

Core docs:

- `docs/architecture.md`
- `docs/technical_plan.md`
- `docs/implementation_plan.md`

## Requirements

- Python 3.11+
- Ticketmaster API key for ingestion
- AgendaLX ingestion does not require an API key
- OpenAI API key for chat through Agno

## Local Setup

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

Run the app:

```bash
uvicorn event_chatbot.main:app --reload
```

Web app:

```text
http://127.0.0.1:8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Chat API

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo\",\"message\":\"I want live jazz in Lisbon tonight under 30 euros\"}"
```

The same endpoint works against the deployed app:

```bash
curl -X POST https://web-production-53075.up.railway.app/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"demo\",\"message\":\"Give me a place to drink wine today in Lisboa\"}"
```

Responses include assistant text plus structured `results`. The frontend event cards are rendered from `results`, not from free-form prose.

## Deterministic Search API

```bash
curl "http://127.0.0.1:8000/events/search?city=Lisbon&q=jazz&limit=5"
```

Deployed:

```bash
curl "https://web-production-53075.up.railway.app/events/search?city=Lisbon&q=jazz&limit=5"
```

## Semantic Ranking

Semantic ranking uses OpenAI embeddings over stored event rows. Retrieval still applies deterministic city/date/status/price filters first; embeddings only influence the final ranking score.

Backfill embeddings after ingesting new events or changing the demo database:

```bash
curl -X POST http://127.0.0.1:8000/embeddings/backfill ^
  -H "Content-Type: application/json" ^
  -d "{\"limit\":1200}"
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

Production health check:

```bash
curl https://web-production-53075.up.railway.app/health
```

The deployed demo can chat and search using the committed DB immediately. New ingestion is optional.

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
