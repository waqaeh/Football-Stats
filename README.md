# Football Stats API

![Tests](https://github.com/waqaeh/Football-Stats/actions/workflows/tests.yml/badge.svg)

A REST API for tracking leagues, teams, players, match events, and Champions League brackets. Built with FastAPI, PostgreSQL, SQLAlchemy, and Docker.

## Running locally

```bash
cp .env.example .env
docker compose up -d
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload    # API docs at http://127.0.0.1:8000/docs
```

## Running tests

Tests use a separate database so they never touch your data. Create it once:

```bash
docker compose exec db createdb -U football football_stats_test
pytest
```
