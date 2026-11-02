from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Prediction, Season, User
from app.schemas.prediction import LeaderboardRow, PredictionCreate, PredictionRead
from app.services.auth import get_current_user
from app.services.predictions import ScoredPrediction, has_kicked_off, leaderboard, score, tie_key, ties_by_key

router = APIRouter(prefix="/seasons/{season_id}/predictions", tags=["predictor"])


def to_read(s: ScoredPrediction) -> PredictionRead:
    p = s.prediction
    return PredictionRead(round=p.round, team_a_id=p.team_a_id, team_b_id=p.team_b_id,
                          winner_team_id=p.winner_team_id, correct=s.correct, points=s.points)


def get_season_or_404(season_id: int, db: Session) -> None:
    if db.get(Season, season_id) is None:
        raise HTTPException(status_code=404, detail="Season not found")


@router.put("", response_model=PredictionRead)
def predict(season_id: int, pick: PredictionCreate, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    """Pick (or change your pick for) the winner of a knockout tie. Allowed until its first leg kicks off."""
    get_season_or_404(season_id, db)
    key = tie_key(pick.round, pick.team_a_id, pick.team_b_id)
    tie = ties_by_key(season_id, db).get(key)
    if tie is None:
        raise HTTPException(status_code=404, detail="No such tie in this season's bracket")
    if pick.winner_team_id not in (pick.team_a_id, pick.team_b_id):
        raise HTTPException(status_code=422, detail="The winner must be one of the tie's two teams")
    if has_kicked_off(tie, datetime.now(timezone.utc)):
        raise HTTPException(status_code=409, detail="This tie has already kicked off")

    _, team_a_id, team_b_id = key
    prediction = db.scalar(select(Prediction).where(
        Prediction.user_id == user.id, Prediction.season_id == season_id, Prediction.round == pick.round,
        Prediction.team_a_id == team_a_id, Prediction.team_b_id == team_b_id,
    ))
    if prediction is None:
        prediction = Prediction(user_id=user.id, season_id=season_id, round=pick.round,
                                team_a_id=team_a_id, team_b_id=team_b_id)
        db.add(prediction)
    prediction.winner_team_id = pick.winner_team_id
    db.commit()
    return to_read(ScoredPrediction(prediction, correct=None, points=0))


@router.get("/me", response_model=list[PredictionRead])
def my_predictions(season_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_season_or_404(season_id, db)
    predictions = db.scalars(
        select(Prediction).where(Prediction.user_id == user.id, Prediction.season_id == season_id)
    ).all()
    return [to_read(s) for s in score(predictions, ties_by_key(season_id, db))]


@router.get("/leaderboard", response_model=list[LeaderboardRow])
def get_leaderboard(season_id: int, db: Session = Depends(get_db)):
    get_season_or_404(season_id, db)
    return [LeaderboardRow(position=i, **row) for i, row in enumerate(leaderboard(season_id, db), start=1)]
