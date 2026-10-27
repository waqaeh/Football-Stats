from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str
    short_name: str = Field(min_length=3, max_length=3)
    stadium: str
    league_id: int


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str
    stadium: str
    league_id: int
