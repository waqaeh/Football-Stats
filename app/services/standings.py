from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Match, MatchStatus, Team

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


def compute_standings(league_id: int, db: Session) -> list[TeamRecord]:
    teams = db.scalars(select(Team).where(Team.league_id == league_id)).all()
    records = {team.id: TeamRecord(team_id=team.id, team_name=team.name) for team in teams}

    finished = db.scalars(
        select(Match).where(Match.league_id == league_id, Match.status == MatchStatus.FINISHED)
    ).all()
    for match in finished:
        for team_id in (match.home_team_id, match.away_team_id):
            if team_id not in records:  # a guest team from another league
                records[team_id] = TeamRecord(team_id=team_id, team_name=db.get(Team, team_id).name)
        records[match.home_team_id].add_result(match.home_score, match.away_score)
        records[match.away_team_id].add_result(match.away_score, match.home_score)

    # Premier League tie-breakers: points, then goal difference, then goals scored.
    return sorted(
        records.values(),
        key=lambda r: (-r.points, -r.goal_difference, -r.goals_for, r.team_name),
    )
