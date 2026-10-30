from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import League, Match, MatchStatus, Team
from app.schemas.match import MatchCreate, MatchRead, MatchUpdate

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchRead, status_code=201)
def create_match(match_in: MatchCreate, db: Session = Depends(get_db)):
    if db.get(League, match_in.league_id) is None:
        raise HTTPException(status_code=404, detail="League not found")
    if db.get(Team, match_in.home_team_id) is None:
        raise HTTPException(status_code=404, detail="Home team not found")
    if db.get(Team, match_in.away_team_id) is None:
        raise HTTPException(status_code=404, detail="Away team not found")
    match = Match(**match_in.model_dump())
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.get("", response_model=list[MatchRead])
def list_matches(
    league_id: int | None = None,
    team_id: int | None = None,
    status: MatchStatus | None = None,
    db: Session = Depends(get_db),
):
    query = select(Match).order_by(Match.kickoff)
    if league_id is not None:
        query = query.where(Match.league_id == league_id)
    if team_id is not None:
        query = query.where(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
    if status is not None:
        query = query.where(Match.status == status)
    return db.scalars(query).all()


@router.get("/{match_id}", response_model=MatchRead)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.patch("/{match_id}", response_model=MatchRead)
def update_match(match_id: int, match_in: MatchUpdate, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    for field, value in match_in.model_dump(exclude_unset=True).items():
        setattr(match, field, value)
    db.commit()
    db.refresh(match)
    return match
