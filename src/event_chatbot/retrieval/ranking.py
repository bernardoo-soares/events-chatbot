from datetime import datetime

from event_chatbot.core.logging import get_logger
from event_chatbot.types.events import EventCandidate
from event_chatbot.types.query import NormalizedQuery, RankedEvent

logger = get_logger(__name__)


def rank_candidates(
    candidates: list[EventCandidate],
    query: NormalizedQuery,
    now: datetime,
) -> list[RankedEvent]:
    logger.info(
        "Ranking candidates candidate_count=%s city=%s used_fts=%s",
        len(candidates),
        query.hard_filters.city,
        query.used_fts,
    )
    lexical_scores = _lexical_scores(candidates, query)
    ranked = [
        _rank_candidate(candidate, query, now, lexical_scores[index])
        for index, candidate in enumerate(candidates)
    ]
    ranked_sorted = sorted(
        ranked,
        key=lambda ranked_event: (
            -ranked_event.score,
            ranked_event.event.start_at,
            ranked_event.event.min_price is None,
            ranked_event.event.min_price if ranked_event.event.min_price is not None else 0,
            ranked_event.event.id,
        ),
    )
    logger.debug(
        "Ranking completed top_event_ids=%s",
        [ranked_event.event.id for ranked_event in ranked_sorted[:10]],
    )
    return ranked_sorted


def _rank_candidate(
    candidate: EventCandidate,
    query: NormalizedQuery,
    now: datetime,
    lexical_score: float,
) -> RankedEvent:
    temporal_score = compute_temporal_score(candidate, query, now)
    price_score = compute_price_score(candidate, query)
    tag_overlap_score = compute_tag_overlap_score(candidate, query)
    score = (
        0.50 * lexical_score
        + 0.25 * temporal_score
        + 0.15 * price_score
        + 0.10 * tag_overlap_score
    )
    return RankedEvent(
        event=candidate,
        score=score,
        lexical_score=lexical_score,
        temporal_score=temporal_score,
        price_score=price_score,
        tag_overlap_score=tag_overlap_score,
    )


def _lexical_scores(candidates: list[EventCandidate], query: NormalizedQuery) -> list[float]:
    if not query.used_fts:
        return [0.5 for _ in candidates]
    values = [candidate.bm25_score for candidate in candidates if candidate.bm25_score is not None]
    if not values:
        return [0.5 for _ in candidates]
    best = min(values)
    worst = max(values)
    if worst == best:
        return [1.0 for _ in candidates]
    return [
        1.0 - (((candidate.bm25_score or worst) - best) / (worst - best))
        for candidate in candidates
    ]


def compute_temporal_score(
    candidate: EventCandidate,
    query: NormalizedQuery,
    now: datetime,
) -> float:
    if candidate.start_at < now:
        return 0.0
    if query.hard_filters.date_from is not None:
        window_start = query.hard_filters.date_from
        delta_hours = abs((candidate.start_at - window_start).total_seconds()) / 3600
        return max(0.0, 1.0 - (delta_hours / 168.0))
    delta_hours = max(0.0, (candidate.start_at - now).total_seconds() / 3600)
    return max(0.0, 1.0 - (delta_hours / 720.0))


def compute_price_score(candidate: EventCandidate, query: NormalizedQuery) -> float:
    max_price = query.hard_filters.max_price
    if max_price is None:
        return 0.5
    if candidate.min_price is None:
        return 0.6
    if candidate.min_price <= max_price:
        return 1.0
    over_budget_ratio = (candidate.min_price - max_price) / max_price
    return max(0.0, 1.0 - over_budget_ratio)


def compute_tag_overlap_score(candidate: EventCandidate, query: NormalizedQuery) -> float:
    query_terms = {term.casefold() for term in [*query.category_boosts, *query.vibe_tags]}
    if not query_terms:
        return 0.5
    event_terms = {
        term.casefold()
        for term in (candidate.category, candidate.subcategory)
        if term is not None
    }
    return len(query_terms & event_terms) / len(query_terms)
