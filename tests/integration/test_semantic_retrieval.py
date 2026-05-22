from datetime import UTC, datetime, timedelta

from event_chatbot.db.connection import connect, transaction
from event_chatbot.db.migrations import initialize_database
from event_chatbot.providers.embeddings import EmbeddingProvider
from event_chatbot.repositories.event_embeddings import EventEmbeddingRepository
from event_chatbot.repositories.events import EventRepository
from event_chatbot.retrieval.semantic import SemanticScorer
from event_chatbot.retrieval.service import RetrievalService
from event_chatbot.types.embeddings import EventEmbeddingUpsert
from event_chatbot.types.ingestion import SourceEvent
from event_chatbot.types.query import HardFilters, NormalizedQuery


class FakeEmbeddingProvider(EmbeddingProvider):
    model = "fake-embedding-model"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _text in texts]


def test_semantic_scores_influence_retrieval_ranking(tmp_path) -> None:
    conn = connect(str(tmp_path / "semantic.sqlite"))
    initialize_database(conn)
    event_repo = EventRepository(conn)
    embedding_repo = EventEmbeddingRepository(conn)
    now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
    with transaction(conn):
        event_repo.upsert_many(
            [
                SourceEvent(
                    source="agendalx",
                    source_event_id="football",
                    title="Lisbon Football Match",
                    city="Lisbon",
                    category="sports",
                    start_at=now + timedelta(hours=2),
                    status="scheduled",
                ),
                SourceEvent(
                    source="agendalx",
                    source_event_id="wine",
                    title="Portuguese Wine Tasting",
                    city="Lisbon",
                    category="food_drink",
                    subcategory="wine",
                    start_at=now + timedelta(hours=8),
                    status="scheduled",
                ),
            ],
            now,
        )
        embedding_repo.upsert_many(
            [
                EventEmbeddingUpsert(
                    event_id=1,
                    model=FakeEmbeddingProvider.model,
                    embedding=[0.0, 1.0],
                    embedded_text_hash="football-hash",
                ),
                EventEmbeddingUpsert(
                    event_id=2,
                    model=FakeEmbeddingProvider.model,
                    embedding=[1.0, 0.0],
                    embedded_text_hash="wine-hash",
                ),
            ],
            now,
        )

    service = RetrievalService(
        event_repository=event_repo,
        clock=lambda: now,
        default_timezone="Europe/Lisbon",
        default_days=30,
        semantic_scorer=SemanticScorer(embedding_repo, FakeEmbeddingProvider()),
    )
    query = NormalizedQuery(
        hard_filters=HardFilters(
            city="Lisbon",
            date_from=now,
            date_to=now + timedelta(days=1),
            statuses=["scheduled"],
        ),
        semantic_terms=["wine", "drinks"],
        used_fts=False,
        limit=2,
    )

    results = service.search(query)

    assert [result.event.title for result in results] == [
        "Portuguese Wine Tasting",
        "Lisbon Football Match",
    ]
    assert results[0].semantic_score == 1.0
    assert results[1].semantic_score == 0.0
