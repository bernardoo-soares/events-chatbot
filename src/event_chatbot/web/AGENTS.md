# AGENTS.md

## Web UI

This folder is a dependency-free static web client served by FastAPI.

## Files

- `index.html`: page structure.
- `styles.css`: responsive visual design.
- `app.js`: chat interaction, session ID, request handling, event-card rendering.

## Rules

- Do not introduce a build step unless explicitly requested.
- Keep the UI driven by `/chat` response data.
- Event cards must render from structured `results`, not from model-generated prose.
- Preserve existing event cards when a later guardrail/clarification response has empty results.
- Clear event cards only on an explicit new session/reset or when replacing them with new results.
- Keep text from overflowing on mobile.
- Avoid adding frontend dependencies for small interactions.

## Known Concern

Some existing text/assets may contain encoding artifacts from earlier edits. If touching nearby UI
strings, keep files UTF-8 and fix visible mojibake only when it is in scope.
