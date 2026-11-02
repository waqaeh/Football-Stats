from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RuleChunk
from app.rag.answer import Answerer, AnswerUnavailable, get_answerer
from app.rag.embeddings import Embedder, get_embedder
from app.rag.retrieval import DEFAULT_MODE, Retrieved, SearchMode, citation, search
from app.schemas.rules import Answer, Question, Source

router = APIRouter(prefix="/rules", tags=["rules Q&A (RAG)"])


def retrieve(question: str, k: int, db: Session, embedder: Embedder, mode: SearchMode = DEFAULT_MODE) -> list[Retrieved]:
    if not db.scalar(select(exists().select_from(RuleChunk))):
        raise HTTPException(status_code=503, detail="The Laws of the Game haven't been loaded: run python -m app.rag.ingest")
    return search(db, embedder, question, k, mode)


def to_sources(results: list[Retrieved]) -> list[Source]:
    return [
        Source(number=i, citation=citation(r.chunk), content=r.chunk.content, score=round(r.score, 4))
        for i, r in enumerate(results, start=1)
    ]


@router.post("/ask", response_model=Answer)
def ask(q: Question, db: Session = Depends(get_db), embedder: Embedder = Depends(get_embedder),
        answerer: Answerer = Depends(get_answerer)):
    """Ask a question about the Laws of the Game. The answer cites the passages it was based on."""
    results = retrieve(q.question, q.top_k, db, embedder)
    sources = to_sources(results)
    try:
        text = answerer.answer(q.question, [r.chunk for r in results])
    except AnswerUnavailable:
        return Answer(answer=None, answered_by=None, sources=sources,
                      note="The language model isn't available, so here are the most relevant passages.")
    return Answer(answer=text, answered_by=answerer.name if text else None, sources=sources)


@router.get("/search", response_model=list[Source])
def search_rules(q: str = Query(min_length=2, max_length=500), k: int = Query(default=5, ge=1, le=10),
                 mode: SearchMode = DEFAULT_MODE, db: Session = Depends(get_db),
                 embedder: Embedder = Depends(get_embedder)):
    """Just the retrieval step: the passages most relevant to `q`. Try mode=hybrid or keyword to compare."""
    return to_sources(retrieve(q, k, db, embedder, mode))
