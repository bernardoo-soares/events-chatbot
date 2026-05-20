# Sprint 09 - Web Chat UI

## Completed At

2026-05-20 20:20 Europe/Lisbon

## Files Changed

- `README.md`
- `docs/implementation_plan.md`
- `docs/logs/sprint_09.md`
- `src/event_chatbot/main.py`
- `src/event_chatbot/web/index.html`
- `src/event_chatbot/web/styles.css`
- `src/event_chatbot/web/app.js`
- `tests/unit/test_health.py`

## Summary

Implemented a browser-based conversational UI served by the existing FastAPI app.

The web app is dependency-free and lives inside the Python package under `src/event_chatbot/web/`. FastAPI serves the launch page at `/` and static assets under `/static`.

The UI uses a pink gradient visual direction with glassmorphism panels, animated background glows, a chat interface, quick prompt chips, a classical three-dot loading state with `I'm thinking`, and a refresh button that starts a new browser session.

The frontend calls the existing `POST /chat` endpoint, stores a browser session id in `localStorage`, renders assistant/user bubbles, and displays the top three structured event results as event cards.

## Tests And Checks

- `python -m compileall src tests`: pass
- `python -m pytest -q`: pass, 35 tests
- `python -m ruff check .`: pass

## Decisions

- Used a static frontend instead of React/Vite to keep launch simple and avoid adding Node/build tooling.
- Event cards render from structured `results`, not from model-generated text.
- Refresh starts a new session id rather than deleting backend chat history.
- Raw `applied_filters` remain hidden from the user interface.

## Known Issues

- No geolocation support yet.
- Assistant text is rendered as safe plain text paragraphs, not full Markdown.
- UI caps visible event cards at three, while the backend still returns up to twenty results.

## Review Status

Ready for review.
