"""Measure retrieval quality on a fixed set of questions.

Run with:  python -m app.rag.evaluate
A question counts as a hit if one of the top-k passages is from the expected Law and contains the expected phrase.
Re-run after every change to chunking or search, and keep the change only if the numbers go up.
"""
import json
from pathlib import Path

from app.database import SessionLocal
from app.rag.embeddings import get_embedder
from app.rag.retrieval import citation, search

QUESTIONS = Path("evals/rules_questions.json")
K = 5


def first_hit_rank(results, expected) -> int | None:
    for rank, result in enumerate(results, start=1):
        chunk = result.chunk
        if expected["law"].startswith("Law "):  # "Law 1" must not match "Law 12 – ..."
            right_law = chunk.section == expected["law"] or chunk.section.startswith(expected["law"] + " ")
        else:
            right_law = expected["law"] in chunk.section
        if right_law and expected["phrase"].lower() in chunk.content.lower():
            return rank
    return None


def main() -> None:
    questions = json.loads(QUESTIONS.read_text())
    embedder = get_embedder()
    print(f"{len(questions)} questions, top {K} passages\n")
    print(f"{'mode':<8} {'hit@1':>6} {'hit@5':>6} {'MRR':>6}")
    misses = {}
    with SessionLocal() as db:
        for mode in ("vector", "keyword", "hybrid"):
            ranks = [first_hit_rank(search(db, embedder, q["question"], K, mode), q) for q in questions]
            hit1 = sum(r == 1 for r in ranks) / len(ranks)
            hit5 = sum(r is not None for r in ranks) / len(ranks)
            mrr = sum(1 / r for r in ranks if r) / len(ranks)  # mean reciprocal rank: 1 if always first, 0.5 if second...
            print(f"{mode:<8} {hit1:>6.0%} {hit5:>6.0%} {mrr:>6.2f}")
            if mode == "hybrid":
                misses = {q["question"]: [citation(r.chunk) for r in search(db, embedder, q["question"], 3, mode)]
                          for q, rank in zip(questions, ranks) if rank is None}
    if misses:
        print("\nHybrid misses (and what it found instead):")
        for question, found in misses.items():
            print(f"  - {question}\n      {' | '.join(found)}")


if __name__ == "__main__":
    main()
