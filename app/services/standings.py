from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import KNOCKOUT_ROUNDS, Match, MatchStatus, Team

POINTS_FOR_WIN = 3
POINTS_FOR_DRAW = 1


@dataclass
class TeamRecord:
    team_id: int
    team_name: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def points(self) -> int:
        return self.won * POINTS_FOR_WIN + self.drawn * POINTS_FOR_DRAW

    def add_result(self, scored: int, conceded: int) -> None:
        self.played += 1
        self.goals_for += scored
        self.goals_against += conceded
        if scored > conceded:
            self.won += 1
        elif scored == conceded:
            self.drawn += 1
        else:
            self.lost += 1


def compute_standings(league_id: int, season_id: int | None, db: Session) -> list[TeamRecord]:
    league_matches = select(Match).where(
        Match.season_id == season_id,
        or_(Match.stage.is_(None), Match.stage.not_in(KNOCKOUT_ROUNDS)),  # knockout games aren't in the table
    )
    matches = db.scalars(league_matches).all()

    # The table lists the teams with fixtures this season, or the league's teams before any are added.
    team_ids = {m.home_team_id for m in matches} | {m.away_team_id for m in matches}
    team_filter = Team.id.in_(team_ids) if team_ids else Team.league_id == league_id
    teams = db.scalars(select(Team).where(team_filter))
    records = {team.id: TeamRecord(team_id=team.id, team_name=team.name) for team in teams}

    for match in matches:
        if match.status == MatchStatus.FINISHED:
            records[match.home_team_id].add_result(match.home_score, match.away_score)
            records[match.away_team_id].add_result(match.away_score, match.home_score)

    # Premier League tie-breakers: points, then goal difference, then goals scored.
    return sorted(
        records.values(),
        key=lambda r: (-r.points, -r.goal_difference, -r.goals_for, r.team_name),
    )
