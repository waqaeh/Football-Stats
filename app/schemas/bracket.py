from pydantic import BaseModel

from app.schemas.match import MatchRead


class BracketSide(BaseModel):
    team_id: int | None
    team_name: str | None
    label: str | None


class BracketTie(BaseModel):
    side_a: BracketSide
    side_b: BracketSide
    legs: list[MatchRead]
    aggregate: tuple[int, int] | None
    winner_team_id: int | None


class BracketRound(BaseModel):
    round: str
    ties: list[BracketTie]


class Bracket(BaseModel):
    season_id: int
    projected: bool
    rounds: list[BracketRound]
