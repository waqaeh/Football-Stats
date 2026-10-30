from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EventType, Match, MatchEvent, MatchStatus, Player
from app.schemas.match_event import MatchEventCreate, MatchEventRead

router = APIRouter(prefix="/matches/{match_id}/events", tags=["match events"])


def get_match_or_404(match_id: int, db: Session) -> Match:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


def scoring_team_id(event: MatchEvent, match: Match) -> int | None:
    """Which team gets a goal from this event (None if it isn't a goal)."""
    if event.type == EventType.GOAL:
        return event.team_id
    if event.type == EventType.OWN_GOAL:
        return match.away_team_id if event.team_id == match.home_team_id else match.home_team_id
    return None


def change_score(match: Match, team_id: int, amount: int) -> None:
    if team_id == match.home_team_id:
        match.home_score += amount
    else:
        match.away_score += amount


@router.post("", response_model=MatchEventRead, status_code=201)
def create_event(match_id: int, event_in: MatchEventCreate, db: Session = Depends(get_db)):
    match = get_match_or_404(match_id, db)
    if match.status == MatchStatus.SCHEDULED:
        raise HTTPException(status_code=409, detail="Match has not started yet")

    player = db.get(Player, event_in.player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    if player.team_id not in (match.home_team_id, match.away_team_id):
        raise HTTPException(status_code=422, detail="Player is not on either team in this match")

    if event_in.related_player_id is not None:
        related = db.get(Player, event_in.related_player_id)
        if related is None:
            raise HTTPException(status_code=404, detail="Related player not found")
        if related.team_id != player.team_id:
            raise HTTPException(status_code=422, detail="Related player must be on the same team")

    # team_id is taken from the player, so the client can't send a wrong one.
    event = MatchEvent(match_id=match_id, team_id=player.team_id, **event_in.model_dump())
    db.add(event)

    scorer = scoring_team_id(event, match)
    if scorer is not None:
        change_score(match, scorer, +1)

    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=list[MatchEventRead])
def list_events(match_id: int, db: Session = Depends(get_db)):
    get_match_or_404(match_id, db)
    query = select(MatchEvent).where(MatchEvent.match_id == match_id).order_by(MatchEvent.minute, MatchEvent.id)
    return db.scalars(query).all()


@router.delete("/{event_id}", status_code=204)
def delete_event(match_id: int, event_id: int, db: Session = Depends(get_db)):
    match = get_match_or_404(match_id, db)
    event = db.get(MatchEvent, event_id)
    if event is None or event.match_id != match_id:
        raise HTTPException(status_code=404, detail="Event not found")

    scorer = scoring_team_id(event, match)
    if scorer is not None:
        change_score(match, scorer, -1)

    db.delete(event)
    db.commit()
