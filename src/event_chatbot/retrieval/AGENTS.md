# AGENTS.md

## Retrieval Layer

This is the core recommendation logic. It must stay deterministic, testable, and grounded in
database rows.

## Pipeline

```text
QuerySpec
-> normalize_query()
-> build_candidate_query()
-> EventRepository.search_candidates()
-> optional SemanticScorer
-> rank_candidates()
-> duplicate-title suppression
-> top N results
```

## Module Roles

- `normalization.py`: converts `QuerySpec` and session state into `NormalizedQuery`.
- `fts.py`: builds safe SQLite FTS query strings.
- `query_builder.py`: builds parameterized SQL from `NormalizedQuery`.
- `semantic.py`: query embedding, cosine similarity, semantic score normalization.
- `embedding_text.py`: deterministic text templates for event/query embeddings.
- `ranking.py`: component scores and final deterministic rank order.
- `scope.py`: deterministic request routing policy for retrieve/clarify/block.
- `service.py`: retrieval orchestration.

## Ranking Rules

- Keep all component scores in `0.0..1.0`.
- Missing embeddings should produce a neutral semantic score, not a failure.
- Semantic score is a soft signal only.
- City/date/status/price hard filters must not be bypassed by semantic similarity.
- Deduplicate repeated event titles after ranking and before returning top results.
- Add tests for any ranking behavior change.

## Query Normalization

- Categories are usually boosts, not hard filters.
- Hard category filters only apply when the user explicitly asks for category-only results.
- Relative dates like `tonight`, `tomorrow`, and `this weekend` are resolved deterministically.
- Session-state merging must be treated carefully; stale filters can distort later queries.

## Semantic Retrieval Notes

The current semantic path computes exact cosine similarity over filtered candidate embeddings. This
is appropriate for the current dataset size. Do not add a vector database or approximate index until
the candidate-level comparison is a demonstrated bottleneck.
