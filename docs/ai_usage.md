# AI Usage Note

This project was designed and scaffolded with AI assistance through Codex.

AI was used for:

- Architecture planning.
- Repository structure planning.
- SQLite schema design.
- Retrieval/ranking design.
- Implementation scaffolding.
- Test generation.
- Documentation drafting.

Human decisions guided the key product and architecture constraints:

- Recommendations must be grounded in a local database.
- Ticketmaster is the first ingestion source.
- Agno is used as a thin LLM orchestration layer.
- Retrieval and ranking remain deterministic Python code.
- SQLite FTS5 is used for lexical search.
- Incremental integer IDs are used for SQLite/FTS compatibility.
- Typed application models live under `types/`.

The LLM layer in the application is intentionally constrained:

- It extracts `QuerySpec` from natural language.
- It renders grounded results into a conversational answer.
- It does not write SQL.
- It does not fetch events during chat.
- It does not invent recommendations.

