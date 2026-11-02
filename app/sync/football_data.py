"""Copies competitions, teams, players and matches from football-data.org into our database.

Every row is matched on external_id, so running a sync again updates rows instead of duplicating them.
"""
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import League, Match, MatchStatus, Player, Season, Team
from app.sync.client import FootballDataClient

POSITIONS = {"Goalkeeper": "GK", "Defence": "DF", "Midfield": "MF", "Offence": "FW"}

STATUSES = {
    "SCHEDULED": MatchStatus.SCHEDULED,
    "TIMED": MatchStatus.SCHEDULED,
    "IN_PLAY": MatchStatus.LIVE,
    "PAUSED": MatchStatus.LIVE,
    "FINISHED": MatchStatus.FINISHED,
    "AWARDED": MatchStatus.FINISHED,
    "POSTPONED": MatchStatus.POSTPONED,
    "SUSPENDED": MatchStatus.POSTPONED,
    "CANCELLED": MatchStatus.POSTPONED,
}


@dataclass
class SyncReport:
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)

    def count(self, model, was_created: bool) -> None:
        counts = self.created if was_created else self.updated
        counts[model.__name__] = counts.get(model.__name__, 0) + 1


def upsert(db: Session, model, external_id: int, report: SyncReport, **fields):
    """Update the row with this external_id, or create it if it doesn't exist yet."""
    row = db.scalar(select(model).where(model.external_id == external_id))
    was_created = row is None
    if was_created:
        row = model(external_id=external_id)
        db.add(row)
    for name, value in fields.items():
        setattr(row, name, value)
    report.count(model, was_created)
    return row


def parse_utc(value: str) -> datetime:
    # "2026-08-21T19:00:00Z": Python 3.10 can't parse the trailing Z, so spell out the UTC offset.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def season_name(start: date, end: date) -> str:
    if start.year == end.year:
        return str(start.year)  # leagues that run within one calendar year, e.g. Brazil
    return f"{start.year}/{str(end.year)[2:]}"  # e.g. "2026/27"


def sync_competition(code: str, client: FootballDataClient, db: Session) -> SyncReport:
    report = SyncReport()

    data = client.get(f"/competitions/{code}")
    league = upsert(db, League, data["id"], report, name=data["name"], country=data["area"]["name"])
    db.flush()  # gives league an id we can use below

    current = data["currentSeason"]
    start, end = date.fromisoformat(current["startDate"]), date.fromisoformat(current["endDate"])
    season = upsert(db, Season, current["id"], report,
                    league_id=league.id, name=season_name(start, end), start_date=start, end_date=end)
    db.flush()

    teams_by_external_id = {}
    for team_data in client.get(f"/competitions/{code}/teams")["teams"]:
        team = upsert(db, Team, team_data["id"], report,
                      name=team_data["shortName"], short_name=team_data["tla"], stadium=team_data["venue"])
        if team.league_id is None:
            # Only set on creation, so syncing the Champions League later won't move Arsenal out of the PL.
            team.league_id = league.id
        db.flush()
        teams_by_external_id[team_data["id"]] = team

        for player_data in team_data["squad"]:
            upsert(db, Player, player_data["id"], report,
                   name=player_data["name"],
                   position=POSITIONS.get(player_data["position"]),
                   nationality=player_data["nationality"],
                   team_id=team.id)

    for match_data in client.get(f"/competitions/{code}/matches", season=start.year)["matches"]:
        full_time = match_data["score"]["fullTime"]
        upsert(db, Match, match_data["id"], report,
               league_id=league.id,
               season_id=season.id,
               home_team_id=teams_by_external_id[match_data["homeTeam"]["id"]].id,
               away_team_id=teams_by_external_id[match_data["awayTeam"]["id"]].id,
               kickoff=parse_utc(match_data["utcDate"]),
               status=STATUSES.get(match_data["status"], MatchStatus.SCHEDULED),
               home_score=full_time["home"] or 0,
               away_score=full_time["away"] or 0)

    db.commit()
    return report
