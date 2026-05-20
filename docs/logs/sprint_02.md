# Sprint 02 - Types And Repositories

## Completed At

2026-05-19 23:19 +01:00

## Files Changed

- `src/event_chatbot/types/ingestion.py`
- `src/event_chatbot/types/events.py`
- `src/event_chatbot/types/query.py`
- `src/event_chatbot/types/chat.py`
- `src/event_chatbot/repositories/events.py`
- `src/event_chatbot/repositories/raw_events.py`
- `src/event_chatbot/repositories/chat_sessions.py`
- `tests/integration/test_repositories.py`

## Summary

Implemented typed application models and repository classes. Added upsert logic for normalized events and raw source payloads, session-state persistence, chat message persistence, and candidate search using hard filters plus optional FTS. Added integration tests for event upsert identity preservation, raw payload upsert, session state round-trip, and candidate search.

## Tests And Checks

- `python -m compileall src tests`: pass
- `python -m pytest -q`: pass, 8 tests
- `ruff check .`: not directly available on PATH
- `python -m ruff check .`: pass

## Decisions

- Used `types/` for typed application models per user preference.
- Added `NormalizedQuery.fts_query` so repository candidate search can receive an already-built FTS query string without owning FTS construction.
- Implemented basic `EventRepository.search_candidates()` now, with deeper query-builder/refinement still planned for Sprint 4.

## Known Issues

- No git repository exists in `C:\Users\berna\Soko_Challenge`.
- `uv` is not installed on PATH, so current checks use `python` and `pip`.
- Query normalization, FTS escaping, and ranking are not implemented yet; they remain Sprint 4 scope.

## Review Status

Ready for review.

