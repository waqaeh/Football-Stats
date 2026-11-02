import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def engine():
    if not settings.test_database_url:
        pytest.exit("TEST_DATABASE_URL is not set (see .env.example)")
    engine = create_engine(settings.test_database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    """A session whose changes are rolled back after each test, so every test starts empty."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


# Helpers that create data through the API, returning the created JSON.

@pytest.fixture
def make_league(client):
    def _make(name="Premier League", country="England"):
        response = client.post("/leagues", json={"name": name, "country": country})
        assert response.status_code == 201, response.text
        return response.json()
    return _make


@pytest.fixture
def make_team(client):
    def _make(league_id, name="Arsenal", short_name="ARS"):
        response = client.post(
            "/teams",
            json={"name": name, "short_name": short_name, "stadium": f"{name} Stadium", "league_id": league_id},
        )
        assert response.status_code == 201, response.text
        return response.json()
    return _make


@pytest.fixture
def make_player(client):
    def _make(team_id, name="Bukayo Saka", shirt_number=7, position="FW"):
        response = client.post(
            "/players",
            json={"name": name, "shirt_number": shirt_number, "position": position,
                  "nationality": "England", "team_id": team_id},
        )
        assert response.status_code == 201, response.text
        return response.json()
    return _make


@pytest.fixture
def make_season(client):
    def _make(league_id, name="2026/27", start_date="2026-08-01", end_date="2027-05-31"):
        response = client.post(
            f"/leagues/{league_id}/seasons",
            json={"name": name, "start_date": start_date, "end_date": end_date},
        )
        assert response.status_code == 201, response.text
        return response.json()
    return _make


@pytest.fixture
def make_match(client, make_season):
    def _make(league_id, home_team_id, away_team_id, status=None, season_id=None, stage=None,
              kickoff="2026-11-01T15:00:00Z"):
        if season_id is None:  # use the league's latest season, creating one if needed
            seasons = client.get(f"/leagues/{league_id}/seasons").json()
            season_id = seasons[-1]["id"] if seasons else make_season(league_id)["id"]
        response = client.post(
            "/matches",
            json={"league_id": league_id, "season_id": season_id, "home_team_id": home_team_id,
                  "away_team_id": away_team_id, "kickoff": kickoff, "stage": stage},
        )
        assert response.status_code == 201, response.text
        match = response.json()
        if status is not None:
            match = client.patch(f"/matches/{match['id']}", json={"status": status}).json()
        return match
    return _make


@pytest.fixture
def setup(make_league, make_team):
    """A Premier League with Arsenal (home side in most tests) and Liverpool."""
    league = make_league()
    arsenal = make_team(league["id"])
    liverpool = make_team(league["id"], name="Liverpool", short_name="LIV")
    return {"league": league, "arsenal": arsenal, "liverpool": liverpool}
