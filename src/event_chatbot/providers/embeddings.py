from typing import Protocol

from openai import OpenAI

from event_chatbot.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProviderError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    model: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str, batch_size: int = 100):
        self.model = model
        self.batch_size = batch_size
        self.client = OpenAI(api_key=api_key, timeout=30.0, max_retries=1)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            logger.info(
                "Requesting OpenAI embeddings model=%s batch_size=%s",
                self.model,
                len(batch),
            )
            try:
                response = self.client.embeddings.create(model=self.model, input=batch)
            except Exception as exc:
                logger.exception("OpenAI embeddings request failed model=%s", self.model)
                raise EmbeddingProviderError(
                    f"OpenAI embeddings request failed: {type(exc).__name__}: {exc}"
                ) from exc

            ordered = sorted(response.data, key=lambda item: item.index)
            embeddings.extend([list(item.embedding) for item in ordered])

        if len(embeddings) != len(texts):
            raise EmbeddingProviderError(
                f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}"
            )
        return embeddings
