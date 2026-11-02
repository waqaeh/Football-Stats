"""Finds the rule passages most relevant to a question.

Two searches run side by side, then their rankings are merged:
- vector search finds passages with a similar *meaning* ("sent off" ~ "red card")
- keyword search finds exact *terms* that embeddings can blur ("DOGSO", "Law 11")
"""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Text, func, select
from sqlalchemy.orm import Session

from app.models import RuleChunk
from app.rag.embeddings import Embedder

SearchMode = Literal["hybrid", "vector", "keyword"]
RRF_K = 60  # the standard constant for reciprocal rank fusion; dampens the gap between rank 1 and rank 2


@dataclass
class Retrieved:
    chunk: RuleChunk
    score: float


def vector_search(db: Session, embedder: Embedder, question: str, limit: int) -> list[RuleChunk]:
    query_vector = embedder.embed_query(question)
    return db.scalars(
        select(RuleChunk).order_by(RuleChunk.embedding.cosine_distance(query_vector)).limit(limit)
    ).all()


def keyword_search(db: Session, question: str, limit: int) -> list[RuleChunk]:
    # plainto_tsquery joins every word with AND, which almost never matches a whole question,
    # so swap to OR and let ts_rank_cd put the passages that match the most words first.
    any_word = func.to_tsquery("english", func.replace(func.plainto_tsquery("english", question).cast(Text), "&", "|"))
    return db.scalars(
        select(RuleChunk)
        .where(RuleChunk.search.op("@@")(any_word))
        .order_by(func.ts_rank_cd(RuleChunk.search, any_word, 2).desc())  # 2: divide by length, so long chunks don't win
        .limit(limit)
    ).all()


# Measured with `python -m app.rag.evaluate` (24 questions): vector 83% hit@5, hybrid 71%, keyword 38%.
# Hybrid ranks exact terms like "DOGSO" higher but loses plainly worded questions, so vector is the default.
DEFAULT_MODE: SearchMode = "vector"


def search(db: Session, embedder: Embedder, question: str, k: int = 5,
           mode: SearchMode = DEFAULT_MODE) -> list[Retrieved]:
    candidates = k * 4
    rankings = []
    if mode in ("hybrid", "vector"):
        rankings.append(vector_search(db, embedder, question, candidates))
    if mode in ("hybrid", "keyword"):
        rankings.append(keyword_search(db, question, candidates))

    # Reciprocal rank fusion: a passage near the top of either list scores well, near the top of both scores best.
    scores: dict[int, float] = {}
    chunks: dict[int, RuleChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0) + 1 / (RRF_K + rank)
            chunks[chunk.id] = chunk
    best = sorted(scores, key=scores.get, reverse=True)[:k]
    return [Retrieved(chunks[chunk_id], scores[chunk_id]) for chunk_id in best]


def citation(chunk: RuleChunk) -> str:
    if chunk.subsection and chunk.section.startswith("Law ") and " – " in chunk.section:
        number, title = chunk.subsection.split(". ", 1)
        return f"{chunk.section.split(' – ')[0]}.{number} ({title}), p. {chunk.page}"
    return f"{chunk.section}, p. {chunk.page}"
