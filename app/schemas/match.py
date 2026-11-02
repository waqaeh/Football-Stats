from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.match import MatchStatus


class MatchCreate(BaseModel):
    league_id: int
    season_id: int
    home_team_id: int
    away_team_id: int
    kickoff: datetime
    stage: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def teams_must_differ(self):
        if self.home_team_id == self.away_team_id:
            raise ValueError("A team cannot play against itself")
        return self


class MatchUpdate(BaseModel):
    status: MatchStatus | None = None
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)
    home_penalties: int | None = Field(default=None, ge=0)
    away_penalties: int | None = Field(default=None, ge=0)


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    season_id: int
    home_team_id: int
    away_team_id: int
    kickoff: datetime
    status: MatchStatus
    home_score: int
    away_score: int
    home_penalties: int | None
    away_penalties: int | None
    stage: str | None
