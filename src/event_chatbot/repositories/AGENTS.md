# AGENTS.md

## Repository Layer

Repositories own SQLite access and translation between rows and typed application objects.

## Current Repositories

- `events.py`: normalized events, candidate search, ID lookups, embedding backfill event loading.
- `raw_events.py`: raw provider payload storage.
- `chat_sessions.py`: explicit chat session state and chat message audit trail.
- `event_embeddings.py`: stored embedding vectors and metadata.

## Rules

- Keep repositories small and explicit.
- Use parameterized SQL only.
- Do not call external APIs from repositories.
- Do not perform ranking or business policy in repositories.
- Convert datetimes consistently with ISO-8601 strings.
- Preserve event IDs across upserts.

## Retrieval Queries

`EventRepository.search_candidates()` should delegate SQL construction to
`retrieval/query_builder.py`. It should return enough data for ranking and response rendering so
retrieval does not need to re-fetch rows.

## Embedding Storage

Embedding vectors are stored as JSON for simplicity. If performance becomes a problem, consider a
BLOB float32 representation or a vector index, but do not introduce that complexity until metrics
show it is needed.
