# Resume 17/05

## Context and challenge framing

We are building a small chatbot API for local discovery as part of a tech challenge.

Challenge requirements already identified:

- Use `Python`
- Use `FastAPI`
- Use `Agno AGI`
- Provide a conversational interface that recommends local events
- Populate a local database through a basic ETL pipeline from at least one external source
- Deliver a working app runnable with `uvicorn`
- Deliver a `README` with run instructions
- Deliver a short note explaining AI-tool usage
- Optional extra: provide the agent log file

The workspace was effectively empty when this discussion started, so there is no pre-existing code architecture constraining the implementation.

## High-level product direction agreed so far

The application should be a **real conversational chatbot**, but recommendations must be:

- deterministic
- grounded in the local database
- not invented by the LLM
- not fetched through live scraping at user request time

This is the main product constraint and it drives the whole architecture.

We explicitly do **not** want:

- open-ended LLM recommendations based on model priors
- free-text-to-SQL generation by the LLM
- live web search or live scraping at chat time
- an over-engineered retrieval stack for a small challenge

## Main problem decomposition

Two main technical challenges were identified:

1. Reliable event ingestion
2. Reliable deterministic retrieval from local data

This led to the conclusion that the application should be treated as a **catalog-search chatbot** rather than as a generic RAG assistant.

That means:

- the LLM handles language understanding and conversational UX
- the application code handles normalization, retrieval, ranking, and grounding
- the database is the source of truth for recommendations

## Architectural proposal discussed

### 1. ETL / ingestion layer

The ingestion layer should run offline or on demand, never during the user chat request.

Recommended behavior:

- fetch data from a real source
- normalize and store data locally
- keep raw payloads for traceability
- deduplicate records
- update records incrementally where possible

Initial source direction discussed:

- prefer a real events API over scraping for v1
- `Ticketmaster Discovery API` was suggested as a strong candidate because it already exposes event search with location/date/category-style filters

The ETL should persist both:

- `raw_source_events`
- normalized `events`-domain tables

Suggested metadata per ingested record:

- `source`
- `source_event_id`
- `source_url`
- `raw_json`
- `ingested_at`
- `last_seen_at`

Deduplication key proposed:

- `(source, source_event_id)`

### 2. Application database

For the challenge, `SQLite` was considered sufficient and desirable because it keeps the app easy to run locally.

Logical data responsibilities identified:

- application data database
- agent/session database

Those should be logically separated even if both are implemented with SQLite.

Application DB stores:

- event truth
- venue truth
- source ingestion data
- retrieval indexes
- search-state data

Agent/session DB stores:

- conversational history
- agent session state managed by Agno

This separation was considered important because grounding becomes clearer when the event catalog is not conflated with agent memory.

### 3. Retrieval layer

This is the most important subsystem.

The agreed architectural principle:

`natural language -> structured intent -> deterministic normalization -> query builder -> SQL/FTS retrieval -> deterministic ranking -> grounded natural-language response`

This specifically rejects:

- `natural language -> LLM writes SQL`

The retrieval engine is therefore not an LLM recommender. It is a deterministic search system with a conversational front-end.

### 4. Conversational layer

The chatbot should still feel like a real assistant, but its intelligence is constrained to two tasks:

- convert human language into structured intent
- convert grounded retrieval results into human-friendly answers

The LLM should **not**:

- invent recommendations
- rank across the full DB by intuition
- fabricate attributes not returned from the DB
- decide results outside the deterministic retrieval service

## Agno / FastAPI / AgentOS conclusions

Current Agno documentation indicated that `AgentOS` is the modern runtime direction and older `FastAPIApp` examples are outdated.

Relevant conclusions from the research phase:

- Agno v2 removed older `FastAPIApp` patterns
- `AgentOS` is the current recommended runtime layer
- Agno supports session/history management
- Agno supports structured output and tool patterns

This matters because a lot of older tutorials online may be stale.

## Recommended request-time workflow

The most detailed workflow discussed was:

1. User sends a chat message.
2. The system loads any prior retrieval state for the current session.
3. An LLM step performs **intent extraction** into a strict predefined schema.
4. Application code merges the new intent with the current session search state.
5. A deterministic normalization layer maps user-level semantics into retrieval terms and filters.
6. The retrieval service builds SQL hard filters and FTS text queries.
7. Candidate rows are fetched from the local DB.
8. Deterministic ranking scores and orders the candidates.
9. Updated search state is persisted.
10. The LLM formats only the returned grounded rows into a conversational answer.

This means the LLM is used twice:

- `natural language -> structured intent`
- `grounded rows -> human-facing response`

Everything in the middle is deterministic Python logic.

## Detailed retrieval model discussed

### Intent extraction schema

We explicitly discussed that the LLM should not output DB-shaped fields directly.

Instead, it should output a **business-level intent schema**.

Example conceptual fields:

- `city`
- `categories`
- `keywords`
- `vibes`
- `date_from`
- `date_to`
- `time_of_day`
- `max_price`
- `budget_level`
- `party_size`
- `radius_km`
- `needs_clarification`
- `clarification_question`

The key design rule:

- this schema represents **user intent**
- this schema does **not** represent raw DB structure

### Why intent schema and DB schema must be separated

We discussed the risk of coupling the LLM output schema directly to the DB schema.

Agreed conclusion:

- the LLM schema should be stable and business-level
- the DB schema can evolve independently
- the mapping layer absorbs DB refactors

Correct layering:

- `IntentSchema`
- `NormalizedQuery`
- `DB query builder`

Incorrect layering:

- `IntentSchema` directly coupled to table structure

This separation was identified as critical for maintainability.

## Example walkthrough used during discussion

Example user message:

> I’m with my girlfriend in Lisbon and I want a romantic spot to have dinner.

This example was mainly used to illustrate the mechanics of intent extraction and normalization.

Important product note identified:

- if the final product scope is strictly `events`, then this query is technically outside scope
- the assistant should then clarify scope or redirect to dinner-related events
- if the scope also includes `places/restaurants`, then the query becomes a valid retrieval example

Assuming support for both `events` and `places`, the discussed workflow was:

1. LLM extracts structured fields such as:
   - `city = Lisbon`
   - `vibe = romantic`
   - `keywords = dinner`
   - `party_size = 2`
   - `time_of_day = evening`
2. Deterministic normalization maps:
   - `romantic` -> internal approved tag cluster
   - `dinner` -> restaurant-like category expansion
3. Query builder constructs:
   - hard SQL filters for city and category
   - FTS search terms derived from the normalized tags and keywords
4. Ranking function scores candidates deterministically
5. LLM presents only those grounded results conversationally

## Nature of the normalization layer

The user explicitly asked how human language becomes filters.

The answer established that the system should use a combination of:

- strict structured extraction via schema
- deterministic normalization dictionaries / mappings
- a deterministic query builder

Important nuance:

- not a giant brittle handwritten parser alone
- not free-form LLM interpretation alone

Instead:

- LLM extracts meaning into typed fields
- application code maps those fields to controlled internal retrieval inputs

Example normalization concepts discussed:

- `vibe=romantic` -> approved internal tags such as:
  - `romantic`
  - `date-night`
  - `intimate`
  - `candlelight`
  - `wine`
  - `rooftop`
- `keyword=dinner` -> approved category expansion such as:
  - `restaurant`
  - `bistro`
  - `wine_bar`

This normalization layer is deterministic and testable.

## Query building and retrieval strategy

The proposed retrieval stack is intentionally simple but strong for this use case.

### Hard filters first

Apply structured filters in SQL before any ranking:

- location
- date range
- category
- price ceiling
- availability
- possibly radius if geolocation exists

### Text search second

Use `SQLite FTS5` over searchable text columns such as:

- title
- description
- venue name
- city
- tags
- possibly editorial labels

This allows matching terms like:

- `jazz`
- `romantic`
- `wine`
- `rooftop`
- `date night`

### Candidate generation

Retrieve a bounded candidate set before final ranking, for example top 100 to 200 rows from the SQL + FTS stage.

### Deterministic reranking

Do not trust raw FTS ordering as final product ranking.

Instead, rerank candidates in Python with a deterministic score.

Illustrative scoring dimensions discussed:

- lexical relevance
- temporal relevance / time proximity
- distance relevance
- budget fit
- tag overlap
- data quality / completeness
- optionally source popularity if available

An illustrative weighted score was discussed conceptually:

- `0.45 * lexical_score`
- `0.25 * temporal_score`
- `0.15 * price_score`
- `0.10 * tag_overlap_score`
- `0.05 * data_quality_score`

This is the actual recommendation engine in the proposed design.

## SQLite indexing decisions discussed

Two SQLite features were highlighted during the brainstorming:

- `FTS5` for text search and BM25 scoring
- `R-Tree` as an optional future optimization for spatial/range-style querying

The current recommendation was:

- use `FTS5` in v1
- treat `R-Tree` as optional, not mandatory for the challenge MVP

## FastAPI surface proposed during brainstorming

Proposed endpoints:

- `POST /chat`
  - receives session id and user message
  - drives the whole conversation + retrieval pipeline
- `POST /ingest`
  - manually triggers ETL ingestion
- `GET /events/search`
  - deterministic debug endpoint to inspect retrieval independently of chat
- `GET /health`
  - health check

The debug endpoint was considered useful because it lets us inspect retrieval quality without conflating issues with the conversational layer.

## Session and retrieval state

Important insight discussed:

- chat history and search state are not the same thing

Agno session history may help the assistant remain conversational, but the application should also maintain explicit search state.

Examples of search state to persist per session:

- last city
- last date range
- last categories
- last keyword/vibe filters
- last result ids

This is what allows follow-up queries such as:

- “what about tomorrow instead?”
- “cheaper options”
- “only evening ones”
- “which is closest?”

The agreed principle:

- conversational continuity should not rely only on latent LLM memory
- retrieval continuity should be represented explicitly in application state

## MCP discussion and conclusions

The possibility of using MCP was discussed.

Example idea:

- user input
- agent calls MCP tool such as `search_events`
- MCP tool queries the DB
- response returns to the agent

Conclusion reached:

- MCP does **not** replace the retrieval logic
- it only changes the integration boundary

Direct in-app pattern:

- `user -> agent -> local Python tool/service -> retrieval service -> DB -> agent -> user`

MCP pattern:

- `user -> agent -> MCP tool call -> MCP server -> retrieval service -> DB -> MCP response -> agent -> user`

Agreed assessment:

- same retrieval brain underneath
- MCP adds protocol and transport layers
- MCP is useful for interoperability
- MCP is not necessary for this challenge’s core architecture
- MCP would add bureaucracy without improving retrieval quality

Recommended stance for the challenge:

- build the retrieval engine as a normal internal service first
- expose it to Agno as a direct tool
- only add MCP later if there is a strategic reason or as an optional extra

## LLM role boundaries clearly defined

The LLM is allowed to:

- interpret natural language
- fill a strict predefined intent schema
- ask clarifying questions when necessary
- turn grounded results into natural language

The LLM is not allowed to:

- write SQL
- retrieve directly from the internet at request time
- invent event recommendations
- fabricate facts not present in the DB output
- perform final recommendation ranking over the whole DB by judgment alone

This boundary was repeatedly reinforced and is central to the design.

## Current recommended tech stack

- `Python`
- `FastAPI`
- `Agno AgentOS`
- `SQLite`
- `SQLite FTS5`
- `SQLModel` or `SQLAlchemy`
- one LLM provider through Agno

The LLM is used only for intent extraction and response rendering, not for raw retrieval or recommendation scoring.

## Key technical principles established

1. Keep retrieval deterministic.
2. Keep event recommendations grounded in local DB data only.
3. Run ingestion offline or on-demand, never inside the chat request.
4. Keep intent schema separate from DB schema.
5. Keep search state separate from chat history.
6. Use the LLM only at constrained boundaries.
7. Use SQL + FTS5 + deterministic reranking instead of vector-heavy overengineering.
8. Prefer direct internal tools over MCP for the first implementation.

## Practical next steps implied by this conversation

The following items were identified as the natural next design steps:

1. Define the exact `QuerySpec` schema.
2. Define the `NormalizedQuery` structure.
3. Define normalization dictionaries / mapping rules.
4. Define the retrieval ranking formula explicitly.
5. Define the initial DB schema for:
   - events
   - venues
   - tags
   - raw ingestion
   - search state
6. Decide the v1 data source concretely.
7. Decide whether v1 scope is strictly `events` or also includes `places`.
8. Scaffold the project structure around the above flow.

## Sources explicitly referenced during the discussion

- Agno runtime storage:
  - `https://docs.agno.com/runtime/storage`
- Agno structured output:
  - `https://docs.agno.com/input-output/structured-output/agent`
- Agno sessions/history:
  - `https://docs.agno.com/basics/sessions/overview`
  - `https://docs.agno.com/basics/sessions/history-management`
  - `https://docs.agno.com/database/session-storage`
  - `https://docs.agno.com/database/chat-history`
- Agno AgentOS:
  - `https://docs.agno.com/agent-os/introduction`
  - `https://docs.agno.com/agent-os/overview`
  - `https://docs.agno.com/agent-os/custom-fastapi/overview`
  - `https://docs.agno.com/agent-os/mcp/mcp`
- Agno MCP:
  - `https://docs.agno.com/demo-os/mcp`
- Agno v2 changelog:
  - `https://docs.agno.com/other/v2-changelog`
- Ticketmaster Discovery API:
  - `https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/`
- FastAPI SQL tutorial:
  - `https://fastapi.tiangolo.com/tutorial/sql-databases/`
- SQLite FTS5:
  - `https://www.sqlite.org/fts5.html`
- SQLite R-Tree:
  - `https://www.sqlite.org/rtree.html`
- MCP architecture/spec references:
  - `https://modelcontextprotocol.io/docs/learn/architecture`
  - `https://modelcontextprotocol.io/specification/2025-11-25`

## Most important final synthesis

The architecture currently favored is:

- ETL ingests event data into a local DB
- Agno handles chat UX, structured intent extraction, and grounded answer rendering
- the application owns deterministic retrieval and ranking
- recommendations always come from the local DB, never from LLM invention

The canonical request path is:

`user message -> QuerySpec -> NormalizedQuery -> SQL/FTS candidate retrieval -> deterministic ranking -> grounded response`

This is the core design decision from the conversation and should be preserved unless a better alternative appears during implementation.
