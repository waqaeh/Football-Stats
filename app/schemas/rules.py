from pydantic import BaseModel, Field


class Question(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class Source(BaseModel):
    number: int  # what the answer's [1], [2] citations refer to
    citation: str  # e.g. "Law 12.4 (Disciplinary action), p. 123"
    content: str
    score: float


class Answer(BaseModel):
    answer: str | None  # None when no language model is available: the sources still answer the question
    answered_by: str | None
    note: str | None = None
    sources: list[Source]
