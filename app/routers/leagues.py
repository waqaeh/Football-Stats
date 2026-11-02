from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import League, Season, Team
from app.schemas.league import LeagueCreate, LeagueRead
from app.schemas.season import SeasonCreate, SeasonRead
from app.schemas.stats import StandingRow, TopScorer
from app.schemas.team import TeamRead
from app.services.standings import compute_standings
from app.services.stats import top_scorers

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.post("", response_model=LeagueRead, status_code=201)
def create_league(league_in: LeagueCreate, db: Session = Depends(get_db)):
    league = League(**league_in.model_dump())
    db.add(league)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="League already exists")
    db.refresh(league)
    return league


@router.get("", response_model=list[LeagueRead])
def list_leagues(db: Session = Depends(get_db)):
    return db.scalars(select(League)).all()


@router.get("/{league_id}", response_model=LeagueRead)
def get_league(league_id: int, db: Session = Depends(get_db)):
    league = db.get(League, league_id)
    if league is None:
        raise HTTPException(status_code=404, detail="League not found")
    return league


@router.get("/{league_id}/teams", response_model=list[TeamRead])
def list_league_teams(league_id: int, db: Session = Depends(get_db)):
    if db.get(League, league_id) is None:
        raise HTTPException(status_code=404, detail="League not found")
    return db.scalars(select(Team).where(Team.league_id == league_id)).all()


@router.post("/{league_id}/seasons", response_model=SeasonRead, status_code=201)
def create_season(league_id: int, season_in: SeasonCreate, db: Session = Depends(get_db)):
    if db.get(League, league_id) is None:
        raise HTTPException(status_code=404, detail="League not found")
    season = Season(league_id=league_id, **season_in.model_dump())
    db.add(season)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Season already exists")
    db.refresh(season)
    return season


@router.get("/{league_id}/seasons", response_model=list[SeasonRead])
def list_seasons(league_id: int, db: Session = Depends(get_db)):
    if db.get(League, league_id) is None:
        raise HTTPException(status_code=404, detail="League not found")
    return db.scalars(select(Season).where(Season.league_id == league_id).order_by(Season.start_date)).all()


def resolve_season_id(league_id: int, season_id: int | None, db: Session) -> int | None:
    """The season to show stats for: the one asked for, or else the league's latest season."""
    if db.get(League, league_id) is None:
        raise HTTPException(status_code=404, detail="League not found")
    if season_id is None:
        latest = select(Season.id).where(Season.league_id == league_id).order_by(Season.start_date.desc()).limit(1)
        return db.scalar(latest)
    season = db.get(Season, season_id)
    if season is None or season.league_id != league_id:
        raise HTTPException(status_code=404, detail="Season not found in this league")
    return season_id


@router.get("/{league_id}/standings", response_model=list[StandingRow])
def get_standings(league_id: int, season_id: int | None = None, db: Session = Depends(get_db)):
    season_id = resolve_season_id(league_id, season_id, db)
    table = compute_standings(league_id, season_id, db)
    return [
        StandingRow(position=position, **asdict(r), goal_difference=r.goal_difference, points=r.points)
        for position, r in enumerate(table, start=1)
    ]


@router.get("/{league_id}/top-scorers", response_model=list[TopScorer])
def get_top_scorers(
    league_id: int,
    season_id: int | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    season_id = resolve_season_id(league_id, season_id, db)
    return top_scorers(season_id, db, limit)
