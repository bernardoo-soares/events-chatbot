# Sprint 03 - Ticketmaster Ingestion

## Completed At

2026-05-19 23:21 +01:00

## Files Changed

- `src/event_chatbot/providers/event_source.py`
- `src/event_chatbot/providers/ticketmaster.py`
- `src/event_chatbot/services/ingestion_service.py`
- `src/event_chatbot/api/dependencies.py`
- `src/event_chatbot/api/routers/ingest.py`
- `src/event_chatbot/main.py`
- `tests/unit/test_ticketmaster_normalization.py`
- `tests/integration/test_ingestion_flow.py`

## Summary

Implemented the event source provider protocol, Ticketmaster Discovery API provider, Ticketmaster payload normalizer, ingestion service, and `POST /ingest` route. The ingestion service stores raw source payloads, normalizes valid events, upserts normalized events, and returns an ingestion summary. Tests use fake providers and sample payloads, not real external API calls.

## Tests And Checks

- `python -m compileall src tests`: pass
- `python -m pytest -q`: pass, 10 tests
- `ruff check .`: not directly available on PATH
- `python -m ruff check .`: pass

## Decisions

- Added `SourcePayload` as the provider return type so raw payload storage always has `source` and `source_event_id`.
- Used FastAPI `Annotated[..., Depends(...)]` style to satisfy Ruff and keep dependency signatures clean.
- Kept CLI ingestion optional; `POST /ingest` is implemented for this sprint.
- Provider failures raise `TicketmasterProviderError`; malformed individual events are counted as ingestion errors.

## Known Issues

- No git repository exists in `C:\Users\berna\Soko_Challenge`.
- `uv` is not installed on PATH, so current checks use `python` and `pip`.
- Manual real Ticketmaster ingestion is not tested yet because API keys are not available.

## Review Status

Ready for review.

