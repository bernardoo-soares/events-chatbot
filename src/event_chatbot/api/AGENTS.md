# AGENTS.md

## API Layer

This folder contains FastAPI dependency wiring and routers. Routers should be thin.

## Responsibilities

- Parse and validate HTTP input.
- Use dependency injection from `dependencies.py`.
- Call a service or retrieval workflow.
- Return Pydantic response models.

## Do Not

- Put business workflows directly in routers.
- Build SQL in routers.
- Call OpenAI, Ticketmaster, or AgendaLX directly from routers.
- Mutate chat state directly in routers.

## Dependency Rules

- `get_db_connection()` initializes schema on request connections.
- Retrieval may receive a `SemanticScorer`; semantic failures must not fail normal search.
- Chat dependencies require OpenAI for request-intent and intent extraction.
- The template response renderer is deterministic and should remain grounded in returned rows.

## Endpoints

- `/health`: basic health.
- `/health/db` and `/health/llm`: debug diagnostics.
- `/events/search`: deterministic retrieval debugging.
- `/chat`: conversational grounded retrieval.
- `/ingest`: manual event ingestion.
- `/embeddings/backfill`: manual event embedding backfill.
