"""Writes an answer from retrieved passages. Swappable: a local model through Ollama, or none at all."""
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import settings
from app.models import RuleChunk
from app.rag.retrieval import citation

# Small local models often paraphrase a rule into its opposite, so the answer must quote the rule word for word first.
SYSTEM_PROMPT = """You answer questions about the football Laws of the Game for referees and fans.

Answer in this format:
Rule: quote the sentence(s) from the extracts that answer the question, word for word, with the extract number, e.g. [1].
In short: explain the quoted rule in plain English in 1-3 sentences. Keep every condition and exception exactly as
written (who, where, which card). Do not add anything that is not in the quote.

Use ONLY the numbered extracts. If they do not answer the question, reply exactly:
"The Laws of the Game extracts I found don't cover this."
"""


class AnswerUnavailable(Exception):
    pass


class Answerer(Protocol):
    name: str | None

    def answer(self, question: str, chunks: list[RuleChunk]) -> str | None: ...


def build_prompt(question: str, chunks: list[RuleChunk]) -> str:
    extracts = "\n\n".join(f"[{i}] {citation(chunk)}\n{chunk.content}" for i, chunk in enumerate(chunks, start=1))
    return f"Extracts from the IFAB Laws of the Game:\n\n{extracts}\n\nQuestion: {question}"


class OllamaAnswerer:
    def __init__(self, url: str, model: str):
        self.url, self.model, self.name = url, model, f"ollama/{model}"

    def answer(self, question: str, chunks: list[RuleChunk]) -> str:
        try:
            response = httpx.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "options": {"temperature": 0},  # no creativity: we want the same, literal answer every time
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_prompt(question, chunks)},
                    ],
                },
                timeout=120,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise AnswerUnavailable(f"Ollama isn't reachable at {self.url}: {error}") from error
        return response.json()["message"]["content"].strip()


class NoAnswerer:
    """Retrieval only, e.g. on a server too small to run a language model."""

    name = None

    def answer(self, question: str, chunks: list[RuleChunk]) -> None:
        return None


@lru_cache
def get_answerer() -> Answerer:
    if settings.llm_provider == "ollama":
        return OllamaAnswerer(settings.ollama_url, settings.ollama_model)
    return NoAnswerer()
