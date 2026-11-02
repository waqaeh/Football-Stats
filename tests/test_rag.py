import hashlib
import math

import httpx
import pytest

from app.main import app
from app.models import RuleChunk
from app.models.rule_chunk import EMBEDDING_DIMENSIONS
from app.rag import answer as answer_module
from app.rag.answer import AnswerUnavailable, OllamaAnswerer, build_prompt, get_answerer
from app.rag.chunking import chunk_pages
from app.rag.embeddings import get_embedder

FILLER = "The referee applies this rule in every match without exception. " * 6


class FakeEmbedder:
    """Bag-of-words vectors: texts sharing words point in similar directions. No model download needed."""

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for word in text.lower().replace("?", " ").replace(".", " ").split():
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIMENSIONS] += 1
        norm = math.sqrt(sum(v * v for v in vector)) or 1
        return [v / norm for v in vector]

    def embed_query(self, text):
        return self._vector(text)

    def embed_passages(self, texts):
        return [self._vector(t) for t in texts]


class FakeAnswerer:
    name = "fake/model"

    def __init__(self):
        self.calls = []

    def answer(self, question, chunks):
        self.calls.append((question, chunks))
        return f"Answer based on {len(chunks)} extracts [1]"


@pytest.fixture
def rules(db):
    """Three rule passages in the database, embedded with the fake embedder."""
    embedder = FakeEmbedder()
    passages = [
        ("Law 11 – Offside", "1. Offside position", 109, "A player is in an offside position if nearer to the goal line than the second-last opponent."),
        ("Law 12 – Fouls and Misconduct", "4. Disciplinary action", 124, "Denying an obvious goal-scoring opportunity DOGSO is a sending-off offence."),
        ("Law 15 – The Throw-in", None, 141, "A goal cannot be scored directly from a throw-in."),
    ]
    for (section, subsection, page, content), vector in zip(passages, embedder.embed_passages([p[3] for p in passages])):
        db.add(RuleChunk(edition="2026/27", section=section, subsection=subsection, page=page,
                         content=content, embedding=vector))
    db.flush()


@pytest.fixture
def fake_answerer():
    answerer = FakeAnswerer()
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_answerer] = lambda: answerer
    yield answerer
    app.dependency_overrides.pop(get_embedder, None)
    app.dependency_overrides.pop(get_answerer, None)


# --- chunking ---------------------------------------------------------------------------------------------

def test_chunks_know_their_law_and_section():
    pages = [
        "Law\n12",
        f"115Laws of the Game 2026/27 | Law 12 | Fouls and Misconduct\n1. Direct free kick\n{FILLER}",
        f"116\n2. Indirect free kick\n{FILLER}",
    ]

    chunks = chunk_pages(pages)

    assert [(c.section, c.subsection, c.page) for c in chunks] == [
        ("Law 12 – Fouls and Misconduct", "1. Direct free kick", 2),
        ("Law 12 – Fouls and Misconduct", "2. Indirect free kick", 3),
    ]


def test_numbered_list_items_are_not_mistaken_for_sections():
    pages = ["Law\n12", f"1. Direct free kick\n{FILLER}\n3. Corner kick\n{FILLER}"]  # 3 can't follow 1

    assert {c.subsection for c in chunk_pages(pages)} == {"1. Direct free kick"}


def test_a_heading_starts_a_new_chunk():
    pages = ["Law\n12", f"{FILLER}\nDenying a goal (DOGSO)\nWhere a player commits an offence the player is sent off."]

    chunks = chunk_pages(pages)

    assert chunks[-1].content.startswith("Denying a goal (DOGSO)")


def test_law_changes_section_is_left_out():
    pages = ["Law\nchanges\n2026/27", f"Amended text with old wording struck through. {FILLER}"]

    assert chunk_pages(pages) == []


# --- API --------------------------------------------------------------------------------------------------

def test_ask_returns_an_answer_with_cited_sources(client, rules, fake_answerer):
    response = client.post("/rules/ask", json={"question": "When is a player in an offside position?", "top_k": 2})

    body = response.json()
    assert response.status_code == 200
    assert body["answer"] == "Answer based on 2 extracts [1]"
    assert body["answered_by"] == "fake/model"
    assert body["sources"][0]["citation"] == "Law 11.1 (Offside position), p. 109"
    assert [s["number"] for s in body["sources"]] == [1, 2]


def test_sources_still_returned_when_the_model_is_down(client, rules, fake_answerer):
    def unavailable(question, chunks):
        raise AnswerUnavailable("Ollama isn't running")
    fake_answerer.answer = unavailable

    body = client.post("/rules/ask", json={"question": "Can you score from a throw-in?"}).json()

    assert body["answer"] is None
    assert "isn't available" in body["note"]
    assert body["sources"][0]["citation"] == "Law 15 – The Throw-in, p. 141"


def test_ask_before_ingesting_explains_what_to_do(client, fake_answerer):
    response = client.post("/rules/ask", json={"question": "What is offside?"})

    assert response.status_code == 503
    assert "app.rag.ingest" in response.json()["detail"]


@pytest.mark.parametrize("mode", ["vector", "keyword", "hybrid"])
def test_every_search_mode_finds_the_matching_rule(client, rules, fake_answerer, mode):
    results = client.get("/rules/search", params={"q": "DOGSO obvious goal-scoring opportunity", "mode": mode}).json()

    assert results[0]["citation"].startswith("Law 12.4")


def test_question_must_not_be_empty(client, fake_answerer):
    assert client.post("/rules/ask", json={"question": ""}).status_code == 422


# --- prompt and model -------------------------------------------------------------------------------------

def test_prompt_numbers_each_extract_with_its_citation():
    chunk = RuleChunk(section="Law 11 – Offside", subsection="1. Offside position", page=109, content="Text.")

    prompt = build_prompt("What is offside?", [chunk])

    assert "[1] Law 11.1 (Offside position), p. 109\nText." in prompt
    assert prompt.endswith("Question: What is offside?")


def test_ollama_answerer_reports_when_ollama_is_not_running(monkeypatch):
    def refuse(*args, **kwargs):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(answer_module.httpx, "post", refuse)

    with pytest.raises(AnswerUnavailable):
        OllamaAnswerer("http://localhost:11434", "llama3.2").answer("What is offside?", [])
