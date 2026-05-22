import math

from event_chatbot.core.logging import get_logger
from event_chatbot.providers.embeddings import EmbeddingProvider, EmbeddingProviderError
from event_chatbot.repositories.event_embeddings import EventEmbeddingRepository
from event_chatbot.retrieval.embedding_text import build_query_embedding_text
from event_chatbot.types.events import EventCandidate
from event_chatbot.types.query import NormalizedQuery

NEUTRAL_SEMANTIC_SCORE = 0.5
logger = get_logger(__name__)


class SemanticScorer:
    def __init__(
        self,
        embedding_repository: EventEmbeddingRepository,
        embedding_provider: EmbeddingProvider,
    ):
        self.embedding_repository = embedding_repository
        self.embedding_provider = embedding_provider

    def score(
        self,
        query: NormalizedQuery,
        candidates: list[EventCandidate],
    ) -> dict[int, float]:
        if not candidates:
            return {}

        event_ids = [candidate.id for candidate in candidates]
        event_embeddings = self.embedding_repository.get_by_event_ids(
            event_ids,
            self.embedding_provider.model,
        )
        if not event_embeddings:
            logger.info("Semantic scoring skipped because no candidate embeddings were found")
            return {}

        query_text = build_query_embedding_text(query)
        try:
            query_embeddings = self.embedding_provider.embed_texts([query_text])
        except EmbeddingProviderError:
            logger.exception("Semantic scoring skipped because query embedding failed")
            return {}
        if not query_embeddings:
            return {}

        query_embedding = query_embeddings[0]
        raw_scores: dict[int, float] = {}
        for candidate in candidates:
            event_embedding = event_embeddings.get(candidate.id)
            if event_embedding is None:
                continue
            similarity = cosine_similarity(query_embedding, event_embedding)
            if similarity is not None:
                raw_scores[candidate.id] = similarity

        return normalize_similarity_scores(raw_scores)


def cosine_similarity(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for left, right in zip(a, b, strict=True):
        dot += left * right
        norm_a += left * left
        norm_b += right * right
    if norm_a == 0.0 or norm_b == 0.0:
        return None
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def normalize_similarity_scores(raw_scores: dict[int, float]) -> dict[int, float]:
    if not raw_scores:
        return {}
    values = list(raw_scores.values())
    best = max(values)
    worst = min(values)
    if best == worst:
        return {event_id: 1.0 for event_id in raw_scores}
    return {
        event_id: max(0.0, min(1.0, (score - worst) / (best - worst)))
        for event_id, score in raw_scores.items()
    }
