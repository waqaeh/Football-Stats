from pydantic import BaseModel, field_validator

from app.models import KNOCKOUT_ROUNDS


class PredictionCreate(BaseModel):
    round: str
    team_a_id: int
    team_b_id: int
    winner_team_id: int

    @field_validator("round")
    @classmethod
    def must_be_a_knockout_round(cls, value: str) -> str:
        if value not in KNOCKOUT_ROUNDS:
            raise ValueError(f"round must be one of {KNOCKOUT_ROUNDS}")
        return value


class PredictionRead(BaseModel):
    round: str
    team_a_id: int
    team_b_id: int
    winner_team_id: int
    correct: bool | None
    points: int


class LeaderboardRow(BaseModel):
    position: int
    username: str
    points: int
    correct: int
    predictions: int
