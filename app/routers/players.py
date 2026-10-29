from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Player, Team
from app.schemas.player import PlayerCreate, PlayerRead

router = APIRouter(prefix="/players", tags=["players"])


@router.post("", response_model=PlayerRead, status_code=201)
def create_player(player_in: PlayerCreate, db: Session = Depends(get_db)):
    if db.get(Team, player_in.team_id) is None:
        raise HTTPException(status_code=404, detail="Team not found")
    player = Player(**player_in.model_dump())
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("", response_model=list[PlayerRead])
def list_players(db: Session = Depends(get_db)):
    return db.scalars(select(Player)).all()


@router.get("/{player_id}", response_model=PlayerRead)
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return player
