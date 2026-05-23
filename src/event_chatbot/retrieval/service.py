from collections.abc import Callable
from datetime import datetime

from event_chatbot.core.logging import get_logger
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.normalization import normalize_query
from event_chatbot.retrieval.ranking import rank_candidates
from event_chatbot.retrieval.semantic import SemanticScorer
from event_chatbot.types.chat import SessionState
from event_chatbot.types.events import EventCandidate
from event_chatbot.types.query import CarryoverField, NormalizedQuery, QuerySpec, RankedEvent

Clock = Callable[[], datetime]
logger = get_logger(__name__)


class RetrievalService:
    def __init__(
        self,
        event_repository: EventRepository,
        clock: Clock,
        default_timezone: str,
        default_days: int,
        default_city: str | None = None,
        semantic_scorer: SemanticScorer | None = None,
    ):
        self.event_repository = event_repository
        self.clock = clock
        self.default_timezone = default_timezone
        self.default_days = default_days
        self.default_city = default_city
        self.semantic_scorer = semantic_scorer

    def normalize(
        self,
        spec: QuerySpec,
        previous: SessionState | None = None,
        carryover_fields: set[CarryoverField] | None = None,
    ) -> NormalizedQuery:
        logger.info(
            "Normalizing query city=%s categories=%s keywords=%s date_text=%s "
            "date_preset=%s date_day=%s date_month=%s date_year=%s "
            "relative_date_amount=%s relative_date_unit=%s date_window_days=%s "
            "default_city=%s previous_state=%s",
            spec.city,
            spec.categories,
            spec.keywords,
            spec.date_text,
            spec.date_preset,
            spec.date_day,
            spec.date_month,
            spec.date_year,
            spec.relative_date_amount,
            spec.relative_date_unit,
            spec.date_window_days,
            self.default_city,
            previous is not None,
        )
        normalized = normalize_query(
            spec,
            previous=previous,
            carryover_fields=carryover_fields,
            now=self.clock(),
            default_timezone=self.default_timezone,
            default_days=self.default_days,
            default_city=self.default_city,
        )
        logger.info(
            "Query normalized city=%s category_boosts=%s fts_terms=%s "
            "used_fts=%s candidate_limit=%s",
            normalized.hard_filters.city,
            normalized.category_boosts,
            normalized.fts_terms,
            normalized.used_fts,
            normalized.candidate_limit,
        )
        return normalized

    def search(self, query: NormalizedQuery) -> list[RankedEvent]:
        logger.info(
            "Searching events city=%s used_fts=%s limit=%s candidate_limit=%s",
            query.hard_filters.city,
            query.used_fts,
            query.limit,
            query.candidate_limit,
        )
        candidates = self.event_repository.search_candidates(query)
        semantic_scores = self._semantic_scores(query, candidates)
        ranked = rank_candidates(candidates, query, self.clock(), semantic_scores)
        unique_ranked = _dedupe_by_title(ranked)
        results = unique_ranked[: query.limit]
        logger.info(
            "Search completed candidate_count=%s unique_count=%s result_count=%s result_ids=%s",
            len(candidates),
            len(unique_ranked),
            len(results),
            [result.event.id for result in results],
        )
        return results

    def _semantic_scores(
        self,
        query: NormalizedQuery,
        candidates: list[EventCandidate],
    ) -> dict[int, float]:
        if self.semantic_scorer is None:
            return {}
        try:
            scores = self.semantic_scorer.score(query, candidates)
        except Exception:
            logger.exception("Semantic scoring failed; continuing with neutral semantic scores")
            return {}
        logger.info("Semantic scoring completed scored_count=%s", len(scores))
        return scores


def _dedupe_by_title(events: list[RankedEvent]) -> list[RankedEvent]:
    seen_titles: set[str] = set()
    unique_events: list[RankedEvent] = []
    for ranked_event in events:
        title_key = " ".join(ranked_event.event.title.casefold().split())
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        unique_events.append(ranked_event)
    return unique_events
