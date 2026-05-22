# AGENTS.md

## Database Layer

This folder owns SQLite connection helpers, schema initialization, and DDL.

## Schema Rules

- `schema.sql` must be safe to run repeatedly.
- Do not delete existing data during initialization.
- Use SQLite FTS5 for `events_fts`.
- Keep `events_fts.rowid = events.id`.
- Keep `event_embeddings.event_id` linked to `events.id` with `ON DELETE CASCADE`.
- Add indexes only when they support a real query path.

## Migration Style

There is no separate migration framework yet. Schema changes are appended to `schema.sql` with
`CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.

When changing schema:

- Update integration tests in `tests/integration/test_db_schema.py`.
- Apply `initialize_database()` to the local DB when local testing needs the new table/index.
- Be explicit about DB file changes, especially `data/demo_events.db`.

## SQL Safety

- Always use parameterized SQL in repositories.
- Do not interpolate user/model input into SQL.
- Keep SQL generation for retrieval in `retrieval/query_builder.py`.
