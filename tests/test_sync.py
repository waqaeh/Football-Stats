import copy
from datetime import date

import httpx
import pytest
from sqlalchemy import func, select

from app.models import League, Match, MatchStatus, Player, Season, Team
from app.sync.client import FootballDataClient
from app.sync.football_data import season_name, sync_competition

COMPETITION = {
    "id": 2021, "name": "Premier League", "area": {"name": "England"},
    "currentSeason": {"id": 2502, "startDate": "2026-08-21", "endDate": "2027-05-30"},
}
TEAMS = {"teams": [
    {"id": 57, "shortName": "Arsenal", "tla": "ARS", "venue": "Emirates Stadium", "squad": [
        {"id": 7784, "name": "Bukayo Saka", "position": "Offence", "nationality": "England"},
        {"id": 9999, "name": "Mystery Man", "position": None, "nationality": "England"},
    ]},
    {"id": 64, "shortName": "Liverpool", "tla": "LIV", "venue": "Anfield", "squad": [
        {"id": 3754, "name": "Mohamed Salah", "position": "Offence", "nationality": "Egypt"},
    ]},
]}
MATCHES = {"matches": [
    {"id": 1, "utcDate": "2026-08-21T19:00:00Z", "status": "FINISHED",
     "homeTeam": {"id": 57}, "awayTeam": {"id": 64}, "score": {"fullTime": {"home": 2, "away": 1}}},
    {"id": 2, "utcDate": "2027-01-10T15:00:00Z", "status": "TIMED",
     "homeTeam": {"id": 64}, "awayTeam": {"id": 57}, "score": {"fullTime": {"home": None, "away": None}}},
]}


class FakeFootballData:
    """Pretends to be football-data.org. Tests can edit `responses` between syncs."""

    def __init__(self):
        self.responses = copy.deepcopy({
            "/v4/competitions/PL": COMPETITION,
            "/v4/competitions/PL/teams": TEAMS,
            "/v4/competitions/PL/matches": MATCHES,
        })

    def client(self, sleep=lambda seconds: None):
        def handle(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=self.responses[request.url.path],
                                  headers={"x-requests-available-minute": "9", "x-requestcounter-reset": "60"})
        http = httpx.Client(base_url="https://api.football-data.org/v4", transport=httpx.MockTransport(handle))
        return FootballDataClient("fake-key", http=http, sleep=sleep)


@pytest.fixture
def fake_api():
    return FakeFootballData()


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_sync_creates_everything(db, fake_api):
    report = sync_competition("PL", fake_api.client(), db)

    assert report.created == {"League": 1, "Season": 1, "Team": 2, "Player": 3, "Match": 2}
    assert db.scalar(select(Season.name)) == "2026/27"


def test_sync_translates_their_format_to_ours(db, fake_api):
    sync_competition("PL", fake_api.client(), db)

    saka = db.scalar(select(Player).where(Player.external_id == 7784))
    mystery = db.scalar(select(Player).where(Player.external_id == 9999))
    finished, upcoming = db.scalars(select(Match).order_by(Match.external_id)).all()

    assert saka.position == "FW"
    assert mystery.position is None
    assert (finished.status, finished.home_score, finished.away_score) == (MatchStatus.FINISHED, 2, 1)
    assert (upcoming.status, upcoming.home_score) == (MatchStatus.SCHEDULED, 0)


def test_running_sync_twice_does_not_duplicate(db, fake_api):
    sync_competition("PL", fake_api.client(), db)

    report = sync_competition("PL", fake_api.client(), db)

    assert report.created == {}
    assert (count(db, League), count(db, Team), count(db, Player), count(db, Match)) == (1, 2, 3, 2)


def test_resync_picks_up_new_results(db, fake_api):
    sync_competition("PL", fake_api.client(), db)
    upcoming = fake_api.responses["/v4/competitions/PL/matches"]["matches"][1]
    upcoming["status"] = "FINISHED"
    upcoming["score"]["fullTime"] = {"home": 0, "away": 3}

    sync_competition("PL", fake_api.client(), db)

    match = db.scalar(select(Match).where(Match.external_id == 2))
    assert (match.status, match.home_score, match.away_score) == (MatchStatus.FINISHED, 0, 3)


def test_resync_moves_transferred_player(db, fake_api):
    sync_competition("PL", fake_api.client(), db)
    teams = fake_api.responses["/v4/competitions/PL/teams"]["teams"]
    teams[1]["squad"].append(teams[0]["squad"].pop(0))  # Saka moves to Liverpool

    sync_competition("PL", fake_api.client(), db)

    saka = db.scalar(select(Player).where(Player.external_id == 7784))
    liverpool = db.scalar(select(Team).where(Team.external_id == 64))
    assert saka.team_id == liverpool.id


def test_synced_table_is_calculated(client, db, fake_api):
    sync_competition("PL", fake_api.client(), db)
    league_id = db.scalar(select(League.id))

    table = client.get(f"/leagues/{league_id}/standings").json()

    assert [(row["team_name"], row["points"]) for row in table] == [("Arsenal", 3), ("Liverpool", 0)]


def test_client_waits_when_rate_limited():
    waits = []
    responses = iter([
        httpx.Response(429, headers={"x-requestcounter-reset": "42"}),
        httpx.Response(200, json={"ok": True}, headers={"x-requests-available-minute": "5"}),
    ])
    http = httpx.Client(base_url="https://api.football-data.org/v4",
                        transport=httpx.MockTransport(lambda request: next(responses)))
    client = FootballDataClient("fake-key", http=http, sleep=waits.append)

    assert client.get("/competitions") == {"ok": True}
    assert waits == [42]


def test_season_names():
    assert season_name(date(2026, 8, 21), date(2027, 5, 30)) == "2026/27"
    assert season_name(date(2026, 4, 1), date(2026, 12, 5)) == "2026"
