from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import KNOCKOUT_ROUNDS, Season, Team
from app.schemas.bracket import Bracket, BracketRound, BracketSide, BracketTie
from app.schemas.match import MatchRead
from app.services.bracket import Tie, projected_bracket, real_bracket
from app.services.standings import compute_standings

router = APIRouter(prefix="/seasons", tags=["brackets"])


def get_season_or_404(season_id: int, db: Session) -> Season:
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    return season


def to_schema(season_id: int, by_round: dict[str, list[Tie]], projected: bool) -> Bracket:
    return Bracket(
        season_id=season_id,
        projected=projected,
        rounds=[
            BracketRound(
                round=round_,
                ties=[
                    BracketTie(
                        side_a=BracketSide(**asdict(tie.side_a)),
                        side_b=BracketSide(**asdict(tie.side_b)),
                        legs=[MatchRead.model_validate(leg) for leg in tie.legs],
                        aggregate=tie.aggregate,
                        winner_team_id=tie.winner_team_id,
                    )
                    for tie in by_round[round_]
                ],
            )
            for round_ in KNOCKOUT_ROUNDS
            if by_round[round_]
        ],
    )


@router.get("/{season_id}/bracket", response_model=Bracket)
def get_bracket(season_id: int, db: Session = Depends(get_db)):
    """The real knockout bracket, built from knockout matches played or scheduled so far."""
    get_season_or_404(season_id, db)
    team_names = dict(db.execute(select(Team.id, Team.name)).all())
    return to_schema(season_id, real_bracket(season_id, db, team_names), projected=False)


@router.get("/{season_id}/bracket/projected", response_model=Bracket)
def get_projected_bracket(season_id: int, db: Session = Depends(get_db)):
    """Who would meet in the knockouts if the league phase ended today."""
    season = get_season_or_404(season_id, db)
    table = compute_standings(season.league_id, season_id, db)
    if len(table) < 24:
        raise HTTPException(status_code=409, detail="A projected bracket needs a league phase of at least 24 teams")
    return to_schema(season_id, projected_bracket(table), projected=True)
