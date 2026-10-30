from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.match_event import EventType


class MatchEventCreate(BaseModel):
    type: EventType
    minute: int = Field(ge=1, le=130)
    player_id: int
    related_player_id: int | None = None

    @model_validator(mode="after")
    def check_related_player(self):
        if self.type == EventType.SUBSTITUTION and self.related_player_id is None:
            raise ValueError("A substitution needs related_player_id (the player coming on)")
        if self.related_player_id == self.player_id:
            raise ValueError("related_player_id must be a different player")
        return self


class MatchEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    team_id: int
    player_id: int
    related_player_id: int | None
    type: EventType
    minute: int
