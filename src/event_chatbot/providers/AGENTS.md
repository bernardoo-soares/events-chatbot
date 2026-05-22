# AGENTS.md

## Provider Layer

Providers are external boundaries. They may call outside APIs or define protocols for those calls.
They should not know about SQLite tables or FastAPI routers.

## Current Providers

- `event_source.py`: event source protocol.
- `ticketmaster.py`: Ticketmaster fetch and normalization.
- `agendalx.py`: AgendaLX fetch and normalization.
- `llm.py`: request-intent, intent, and response-renderer protocols.
- `agno_llm.py`: Agno/OpenAI LLM implementation for request intent and QuerySpec extraction.
- `template_response.py`: deterministic grounded response rendering.
- `embeddings.py`: embedding protocol and OpenAI embedding implementation.

## Rules

- Providers do not write to the database.
- Providers do not perform business workflow orchestration.
- Provider errors should be explicit runtime errors with useful messages.
- Automated tests should use fake providers or `httpx.MockTransport`.
- Do not make real network calls in tests.

## LLM Boundary

The LLM extracts structured data. It must not:

- choose final events,
- create event facts,
- write SQL,
- call event providers during chat.

## Embedding Boundary

OpenAI embeddings convert deterministic text into vectors. They are not a recommendation engine by
themselves. Semantic scores are computed in retrieval and used only as soft ranking signals.
