from collections.abc import Callable
from datetime import datetime

from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.normalization import normalize_query
from event_chatbot.retrieval.ranking import rank_candidates
from event_chatbot.types.chat import SessionState
from event_chatbot.types.query import NormalizedQuery, QuerySpec, RankedEvent

Clock = Callable[[], datetime]


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
        return normalize_query(
            spec,
            previous=previous,
            now=self.clock(),
            default_timezone=self.default_timezone,
            default_days=self.default_days,
        )

    def search(self, query: NormalizedQuery) -> list[RankedEvent]:
        candidates = self.event_repository.search_candidates(query)
        ranked = rank_candidates(candidates, query, self.clock())
        return ranked[: query.limit]

