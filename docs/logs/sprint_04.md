# Sprint 04 - QuerySpec, Normalization, And Retrieval

## Completed At

2026-05-19 23:24 +01:00

## Files Changed

- `src/event_chatbot/retrieval/fts.py`
- `src/event_chatbot/retrieval/normalization.py`
- `src/event_chatbot/retrieval/query_builder.py`
- `src/event_chatbot/retrieval/ranking.py`
- `src/event_chatbot/retrieval/service.py`
- `src/event_chatbot/repositories/events.py`
- `src/event_chatbot/api/dependencies.py`
- `src/event_chatbot/api/routers/events.py`
- `src/event_chatbot/main.py`
- `tests/unit/test_fts.py`
- `tests/unit/test_normalization.py`
- `tests/unit/test_ranking.py`
- `tests/unit/test_query_builder.py`
- `tests/integration/test_retrieval_flow.py`

## Summary

Implemented deterministic retrieval: `QuerySpec` normalization into `NormalizedQuery`, FTS query construction, SQL candidate query builder, ranking component scoring, retrieval service orchestration, and `GET /events/search`. Added tests for FTS construction, normalization rules, ranking formulas, query builder behavior, and seeded end-to-end retrieval.

## Tests And Checks

- `python -m compileall src tests`: pass
- `python -m pytest -q`: pass, 18 tests
- `ruff check .`: not directly available on PATH
- `python -m ruff check .`: pass

## Decisions

- Added `NormalizedQuery.fts_query` as the built FTS string and kept `fts_terms` as the traceable source terms.
- Kept category suggestions as soft boosts unless `hard_category_only=True`.
- Moved SQL candidate query construction into `retrieval/query_builder.py` and made `EventRepository.search_candidates()` delegate to it.
- Added `/events/search` as an LLM-free debug endpoint.

## Known Issues

- No git repository exists in `C:\Users\berna\Soko_Challenge`.
- `uv` is not installed on PATH, so current checks use `python` and `pip`.
- Manual real Ticketmaster ingestion/search is not tested yet because API keys are not available.
- Agno LLM integration and `/chat` are not implemented yet; they remain Sprint 5 and Sprint 6.

## Review Status

Ready for review.

