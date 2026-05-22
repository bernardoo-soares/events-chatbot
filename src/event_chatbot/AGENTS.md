# AGENTS.md

## Package Context

`event_chatbot` is the application package. It contains the FastAPI app, database layer,
providers, repositories, services, retrieval logic, Pydantic types, and static web UI.

The dependency direction should stay simple:

```text
api -> services -> repositories/providers/retrieval -> types/core/db
```

Avoid imports that make lower-level modules depend on API routers or FastAPI objects.

## Important Modules

- `main.py`: creates the FastAPI app, mounts static assets, registers routers, and logs requests.
- `core/`: settings, logging, clock helpers.
- `db/`: SQLite connection and schema initialization.
- `types/`: Pydantic contracts used across the app.
- `providers/`: external API and model provider boundaries.
- `repositories/`: SQLite persistence.
- `services/`: orchestration workflows.
- `retrieval/`: normalization, FTS, semantic scoring, ranking.
- `web/`: static browser UI.

## Rules

- Keep model/LLM behavior outside repositories.
- Keep SQLite details outside providers.
- Keep API request parsing outside retrieval.
- Keep event recommendations grounded in repository-returned event rows.
- If a module needs a fake in tests, prefer a small protocol at the provider boundary.
