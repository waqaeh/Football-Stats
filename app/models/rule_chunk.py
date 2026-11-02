from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, Index, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

EMBEDDING_DIMENSIONS = 384  # size of the vectors made by BAAI/bge-small-en-v1.5


class RuleChunk(Base):
    """A passage from the IFAB Laws of the Game, stored for retrieval-augmented generation (RAG)."""

    __tablename__ = "rule_chunks"
    __table_args__ = (
        # HNSW: a graph index that finds the nearest vectors without comparing against every row.
        Index("rule_chunks_embedding_idx", "embedding", postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("rule_chunks_search_idx", "search", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edition: Mapped[str] = mapped_column(String(10))  # e.g. "2026/27"
    section: Mapped[str] = mapped_column(String(100))
    subsection: Mapped[str | None] = mapped_column(String(100))
    page: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    # Kept up to date by Postgres from `content`, for keyword (full-text) search.
    search = mapped_column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True))
