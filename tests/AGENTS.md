# AGENTS.md

## Tests

The test suite must stay deterministic and offline.

## Rules

- Do not require real OpenAI, Ticketmaster, or AgendaLX calls in automated tests.
- Use fake providers, fake embedding providers, or `httpx.MockTransport`.
- Prefer focused tests for ranking, normalization, query building, and repository behavior.
- Integration tests should use temporary SQLite databases through `tmp_path`.
- If schema changes, update `tests/integration/test_db_schema.py`.
- If API dependency behavior changes, override dependencies in FastAPI tests.

## Useful Commands

```bash
python -m pytest -q
python -m pytest tests/unit -q
python -m pytest tests/integration -q
```

## Current Coverage Areas

- Config aliases.
- DB schema and FTS triggers.
- Repository upserts and session state.
- Ingestion flow with fake providers.
- AgendaLX and Ticketmaster normalization.
- Query normalization, FTS, ranking, and semantic scoring.
- Chat API guardrails and grounded result flow.
- Static web route serving.
