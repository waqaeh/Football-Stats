from functools import lru_cache
from typing import Protocol

from app.config import settings

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # small (~130 MB), runs on a laptop CPU, no API key


class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Turns text into vectors with a local model. Similar meanings end up as nearby vectors."""

    def __init__(self):
        from fastembed import TextEmbedding  # imported here so the API starts fast and tests never load it

        self.model = TextEmbedding(EMBEDDING_MODEL, cache_dir=settings.embedding_cache_dir)

    def embed_query(self, text: str) -> list[float]:
        # bge models embed questions slightly differently from the passages they should match.
        return next(iter(self.model.query_embed(text))).tolist()

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self.model.passage_embed(texts)]


@lru_cache
def get_embedder() -> Embedder:
    """Loaded once, on first use. A FastAPI dependency, so tests can swap in a fake."""
    return FastEmbedder()
