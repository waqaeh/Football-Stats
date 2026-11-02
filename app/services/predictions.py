from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MatchStatus, Prediction, Team, User
from app.services.bracket import Tie, real_bracket

# Later rounds are harder to call, so they're worth more.
ROUND_POINTS = {"PLAYOFFS": 1, "LAST_16": 2, "QUARTER_FINALS": 4, "SEMI_FINALS": 8, "FINAL": 16}


def tie_key(round_: str, team_1: int, team_2: int) -> tuple[str, int, int]:
    return round_, min(team_1, team_2), max(team_1, team_2)


def ties_by_key(season_id: int, db: Session) -> dict[tuple[str, int, int], Tie]:
    team_names = dict(db.execute(select(Team.id, Team.name)).all())
    return {
        tie_key(tie.round, tie.side_a.team_id, tie.side_b.team_id): tie
        for ties in real_bracket(season_id, db, team_names).values()
        for tie in ties
    }


def has_kicked_off(tie: Tie, now: datetime) -> bool:
    first_leg = tie.legs[0]
    return first_leg.status != MatchStatus.SCHEDULED or first_leg.kickoff <= now


@dataclass
class ScoredPrediction:
    prediction: Prediction
    correct: bool | None  # None until the tie is decided
    points: int


def score(predictions: list[Prediction], ties: dict) -> list[ScoredPrediction]:
    scored = []
    for p in predictions:
        tie = ties.get((p.round, p.team_a_id, p.team_b_id))
        winner = tie.winner_team_id if tie else None
        correct = None if winner is None else winner == p.winner_team_id
        scored.append(ScoredPrediction(p, correct, ROUND_POINTS[p.round] if correct else 0))
    return scored


def leaderboard(season_id: int, db: Session) -> list[dict]:
    ties = ties_by_key(season_id, db)
    rows = {}
    predictions = db.scalars(select(Prediction).where(Prediction.season_id == season_id)).all()
    usernames = dict(db.execute(select(User.id, User.username)).all())
    for s in score(predictions, ties):
        row = rows.setdefault(s.prediction.user_id, {
            "username": usernames[s.prediction.user_id], "points": 0, "correct": 0, "predictions": 0,
        })
        row["points"] += s.points
        row["correct"] += bool(s.correct)
        row["predictions"] += 1
    return sorted(rows.values(), key=lambda r: (-r["points"], -r["correct"], r["username"]))
