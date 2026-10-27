from pydantic import BaseModel, ConfigDict


class LeagueCreate(BaseModel):
    name: str
    country: str


class LeagueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
