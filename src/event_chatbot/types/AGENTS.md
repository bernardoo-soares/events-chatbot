# AGENTS.md

## Types Layer

This folder contains Pydantic business contracts. These models are not ORM models and should not
contain database or provider logic.

## Main Contracts

- `events.py`: normalized event rows and event candidates.
- `ingestion.py`: ingestion requests, source payloads, source events, summaries.
- `query.py`: request intent, QuerySpec, NormalizedQuery, RankedEvent.
- `chat.py`: chat request/response, messages, session state.
- `embeddings.py`: embedding vectors and backfill summary.

## Rules

- Keep models focused on stable application concepts.
- Use `Field(default_factory=list)` for mutable list defaults.
- Avoid leaking provider-specific payload structures into shared types.
- Avoid leaking SQLite row shape when a more meaningful application concept exists.
- When adding fields to response models, update tests that serialize API responses.

## Query Contracts

`QuerySpec` is model-extracted intent. `NormalizedQuery` is deterministic retrieval input.
Do not pass raw `QuerySpec` to SQL builders.

`RankedEvent` should expose ranking components when useful for debugging. Component scores should
stay numeric and bounded.
