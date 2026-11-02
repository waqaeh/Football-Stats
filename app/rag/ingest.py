"""Load the Laws of the Game into the database for RAG.

Run with:  python -m app.rag.ingest
Downloads the PDF (once), splits it into chunks, embeds them and replaces this edition's chunks.
"""
from pathlib import Path

import httpx
from sqlalchemy import delete

from app.database import SessionLocal
from app.models import RuleChunk
from app.rag.chunking import chunk_pages, read_pages
from app.rag.embeddings import get_embedder

EDITION = "2026/27"
PDF_URL = "https://downloads.theifab.com/downloads/laws-of-the-game-202627-single-pages?l=en"
PDF_PATH = Path("data/laws-of-the-game-2026-27.pdf")  # data/ is git-ignored: the PDF is IFAB's, not ours to commit


def download_pdf() -> Path:
    if not PDF_PATH.exists():
        print(f"Downloading the Laws of the Game {EDITION}...")
        PDF_PATH.parent.mkdir(exist_ok=True)
        response = httpx.get(PDF_URL, follow_redirects=True, timeout=120)
        response.raise_for_status()
        PDF_PATH.write_bytes(response.content)
    return PDF_PATH


def main() -> None:
    chunks = chunk_pages(read_pages(str(download_pdf())))
    print(f"Split into {len(chunks)} chunks. Embedding (the first run downloads the embedding model)...")

    # Embed each passage with its location, so "Law 11 – Offside" helps match questions about offside.
    texts = [f"{c.section}. {c.subsection or ''}\n{c.content}" for c in chunks]
    vectors = get_embedder().embed_passages(texts)

    with SessionLocal() as db:
        db.execute(delete(RuleChunk).where(RuleChunk.edition == EDITION))  # re-running replaces, never duplicates
        db.add_all(
            RuleChunk(edition=EDITION, section=c.section, subsection=c.subsection, page=c.page,
                      content=c.content, embedding=vector)
            for c, vector in zip(chunks, vectors)
        )
        db.commit()
    print(f"Stored {len(chunks)} chunks of the {EDITION} Laws of the Game.")


if __name__ == "__main__":
    main()
