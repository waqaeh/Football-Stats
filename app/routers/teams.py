from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import League, Player, Team
from app.schemas.player import PlayerRead
from app.schemas.team import TeamCreate, TeamRead

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamRead, status_code=201)
def create_team(team_in: TeamCreate, db: Session = Depends(get_db)):
    if db.get(League, team_in.league_id) is None:
        raise HTTPException(status_code=404, detail="League not found")
    team = Team(**team_in.model_dump())
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Team already exists")
    db.refresh(team)
    return team


@router.get("", response_model=list[TeamRead])
def list_teams(db: Session = Depends(get_db)):
    return db.scalars(select(Team)).all()


@router.get("/{team_id}", response_model=TeamRead)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/{team_id}/players", response_model=list[PlayerRead])
def list_team_players(team_id: int, db: Session = Depends(get_db)):
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return db.scalars(select(Player).where(Player.team_id == team_id)).all()
