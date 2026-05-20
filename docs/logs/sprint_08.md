# Sprint 08 - AgendaLX Lisbon Ingestion

## Completed At

2026-05-20 19:10 Europe/Lisbon

## Files Changed

- `.env.example`
- `README.md`
- `docs/architecture.md`
- `docs/implementation_plan.md`
- `docs/logs/sprint_08.md`
- `src/event_chatbot/api/dependencies.py`
- `src/event_chatbot/api/routers/ingest.py`
- `src/event_chatbot/core/config.py`
- `src/event_chatbot/providers/agendalx.py`
- `src/event_chatbot/providers/event_source.py`
- `src/event_chatbot/services/ingestion_factory.py`
- `src/event_chatbot/services/ingestion_service.py`
- `src/event_chatbot/types/ingestion.py`
- `src/event_chatbot/types/query.py`
- `tests/integration/test_ingestion_flow.py`
- `tests/unit/test_agendalx_provider.py`
- `tests/unit/test_normalization.py`

## Summary

Implemented AgendaLX as a first-class event source for Lisbon.

AgendaLX ingestion uses the existing provider abstraction and stores data through the same `SourcePayload -> SourceEvent -> IngestionService -> repositories` pipeline as Ticketmaster.

The provider fetches `per_page=100`, paginates by `page`, stops at request size or exhausted pages, and stores stable source identities with `source="agendalx"` and `source_event_id=str(id)`.

AgendaLX normalization maps title, description, venue, category, tags, dates, URL, and image into the existing `SourceEvent` schema. It uses fixed Lisbon metadata and drops events that ended before today, while keeping currently active long-running events.

Added `source` to `IngestionRequest`, defaulting to `ticketmaster`, and introduced a source-aware ingestion factory used by `/ingest`.

Added `scheduled` to the default retrieval status filter so AgendaLX rows are visible in deterministic search and chat.

## Tests And Checks

- `python -m compileall src tests`: pass
- `python -m pytest -q`: pass, 33 tests
- `python -m ruff check .`: pass
- Manual live AgendaLX smoke test: pass
- Manual Lisbon retrieval after AgendaLX ingestion: pass, 20 results returned

## Manual Smoke Test Result

Request:

```text
source=agendalx
city=Lisbon
size=300
```

Result:

```text
fetched=300
inserted=300
updated=0
errors=0
```

Stored event counts after smoke test:

```text
agendalx | Lisbon | 300
ticketmaster | Lisbon | 2
ticketmaster | Madrid | 100
ticketmaster | Paris | 2
```

## Decisions

- Did not change the SQLite schema. AgendaLX adapts to the existing event schema.
- Kept Ticketmaster as the default ingestion source for backward compatibility.
- Filtered past AgendaLX events before raw payload insertion to avoid polluting `raw_events` and `events`.
- Used conservative price handling. AgendaLX price fields are not parsed into numeric values yet unless a future parser can do so safely.

## Known Issues

- AgendaLX prices are not normalized yet.
- AgendaLX latitude/longitude are not normalized yet.
- Cross-source deduplication is not implemented yet, so the same real-world event can still appear from multiple sources.

## Review Status

Ready for review.
