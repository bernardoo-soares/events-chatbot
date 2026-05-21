from collections.abc import Callable
from datetime import datetime

from event_chatbot.core.logging import get_logger
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.normalization import normalize_query
from event_chatbot.retrieval.ranking import rank_candidates
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent

Clock = Callable[[], datetime]
logger = get_logger(__name__)


class RetrievalService:
    def __init__(
        self,
        event_repository: EventRepository,
        clock: Clock,
        default_timezone: str,
        default_days: int,
    ):
        self.event_repository = event_repository
        self.clock = clock
        self.default_timezone = default_timezone
        self.default_days = default_days

    def normalize(self, spec: QuerySpec, previous: SessionState | None = None) -> NormalizedQuery:
        logger.info(
            "Normalizing query city=%s categories=%s keywords=%s date_text=%s previous_state=%s",
            spec.city,
            spec.categories,
            spec.keywords,
            spec.date_text,
            previous is not None,
        )
        normalized = normalize_query(
            spec,
            previous=previous,
            now=self.clock(),
            default_timezone=self.default_timezone,
            default_days=self.default_days,
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
        ranked = rank_candidates(candidates, query, self.clock())
        results = ranked[: query.limit]
        logger.info(
            "Search completed candidate_count=%s result_count=%s result_ids=%s",
            len(candidates),
            len(results),
            [result.event.id for result in results],
        )
        return results
