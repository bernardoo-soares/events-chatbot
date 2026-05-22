# AGENTS.md

## Service Layer

Services orchestrate workflows across providers, repositories, retrieval, and transactions.

## Current Services

- `chat_service.py`: full chat workflow, scope decision, intent extraction, retrieval, state
  persistence, response rendering.
- `ingestion_service.py`: provider fetch, raw event storage, normalization, event upsert.
- `ingestion_factory.py`: source-specific ingestion service construction.
- `embedding_service.py`: event embedding backfill.

## Rules

- Keep transaction boundaries explicit.
- Do not put HTTP-specific behavior in services except where the existing code already raises
  FastAPI `HTTPException` for API-facing service construction failures.
- Services may coordinate repositories and providers, but they should not hide ranking logic.
- Chat must append user and assistant messages consistently.
- If a guardrail blocks or clarifies, do not overwrite prior frontend cards by returning fake
  event results.

## Embedding Backfill

Backfill should:

- build deterministic event embedding text,
- hash that text,
- skip unchanged rows for the same model,
- call the embedding provider in batches,
- upsert embeddings transactionally,
- return a clear summary.
