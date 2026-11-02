FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EMBEDDING_CACHE_DIR=/app/models

WORKDIR /app

# Dependencies first: this layer is cached and only rebuilt when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model while building, so the first question after a deploy isn't slow.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/models')"

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Don't run as root: if the app were ever compromised, the attacker gets as few permissions as possible.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
# Bring the database schema up to date, then start the API. Hosts like Render set $PORT.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
