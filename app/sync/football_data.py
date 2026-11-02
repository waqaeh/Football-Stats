"""Copies competitions, teams, players and matches from football-data.org into our database.

Every row is matched on external_id, so running a sync again updates rows instead of duplicating them.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
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


def sync_competition(code: str, client: FootballDataClient, db: Session, include_teams: bool = True,
                     season_year: int | None = None) -> SyncReport:
    """Sync one competition's current season, or a past one (season_year=2025 means 2025/26).

    include_teams=False skips teams and squads (the slow part) to just refresh results.
    """
    report = SyncReport()

    data = client.get(f"/competitions/{code}")
    league = upsert(db, League, data["id"], report, name=data["name"], country=data["area"]["name"])
    db.flush()  # gives league an id we can use below

    year = season_year or date.fromisoformat(data["currentSeason"]["startDate"]).year
    matches = client.get(f"/competitions/{code}/matches", season=year)["matches"]
    season_data = data["currentSeason"] if season_year is None else matches[0]["season"]
    start, end = date.fromisoformat(season_data["startDate"]), date.fromisoformat(season_data["endDate"])
    season = upsert(db, Season, season_data["id"], report,
                    league_id=league.id, name=season_name(start, end), start_date=start, end_date=end)
    db.flush()

    if include_teams:
        # Squads only make sense for the current season: an old squad would move transferred players back.
        sync_teams(code, client, db, league, report, year, include_squads=season_year is None)
    sync_matches(matches, db, league, season, report)

    db.commit()
    return report


def sync_teams(code: str, client: FootballDataClient, db: Session, league: League, report: SyncReport,
               year: int, include_squads: bool = True) -> None:
    for team_data in client.get(f"/competitions/{code}/teams", season=year)["teams"]:
        team = upsert(db, Team, team_data["id"], report,
                      name=team_data["shortName"], short_name=team_data["tla"], stadium=team_data["venue"],
                      crest_url=team_data.get("crest"))
        if team.league_id is None:
            # Only set on creation, so syncing the Champions League later won't move Arsenal out of the PL.
            team.league_id = league.id
        db.flush()

        for player_data in team_data["squad"] if include_squads else []:
            upsert(db, Player, player_data["id"], report,
                   name=player_data["name"],
                   position=POSITIONS.get(player_data["position"]),
                   nationality=player_data["nationality"],
                   team_id=team.id)


def match_score(score: dict) -> tuple[int, int, int | None, int | None]:
    """(home goals, away goals, home penalties, away penalties).

    football-data.org's fullTime score includes shootout penalties (a 1-1 won 4-3 on pens is "5-4"),
    so for shootouts the real score is regular time plus extra time.
    """
    if score.get("duration") == "PENALTY_SHOOTOUT":
        regular, extra, pens = score["regularTime"], score.get("extraTime") or {}, score["penalties"]
        return (regular["home"] + (extra.get("home") or 0), regular["away"] + (extra.get("away") or 0),
                pens["home"], pens["away"])
    full_time = score["fullTime"]
    return full_time["home"] or 0, full_time["away"] or 0, None, None


def sync_matches(matches: list[dict], db: Session, league: League, season: Season, report: SyncReport) -> None:
    team_ids = dict(db.execute(select(Team.external_id, Team.id).where(Team.external_id.is_not(None))).all())

    for match_data in matches:
        home_id = team_ids.get(match_data["homeTeam"]["id"])
        away_id = team_ids.get(match_data["awayTeam"]["id"])
        if home_id is None or away_id is None:
            continue  # e.g. a knockout tie whose teams aren't decided yet ("TBD")

        home_score, away_score, home_penalties, away_penalties = match_score(match_data["score"])
        upsert(db, Match, match_data["id"], report,
               league_id=league.id,
               season_id=season.id,
               home_team_id=home_id,
               away_team_id=away_id,
               kickoff=parse_utc(match_data["utcDate"]),
               status=STATUSES.get(match_data["status"], MatchStatus.SCHEDULED),
               home_score=home_score,
               away_score=away_score,
               home_penalties=home_penalties,
               away_penalties=away_penalties,
               stage=match_data.get("stage"))


def seconds_until_next_sync(db: Session, now: datetime) -> int:
    """Sync every minute while matches are being played, otherwise wait until the next kickoff (at most 15 minutes)."""
    playing = db.scalar(
        select(Match.id).where(
            Match.status.in_([MatchStatus.LIVE, MatchStatus.SCHEDULED]),
            Match.kickoff <= now,
            Match.kickoff > now - timedelta(hours=3),
        ).limit(1)
    )
    if playing is not None:
        return 60

    next_kickoff = db.scalar(
        select(func.min(Match.kickoff)).where(Match.status == MatchStatus.SCHEDULED, Match.kickoff > now)
    )
    if next_kickoff is None:
        return 15 * 60
    return int(min(max((next_kickoff - now).total_seconds(), 60), 15 * 60))
