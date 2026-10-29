from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class PlayerCreate(BaseModel):
    name : str
    shirt_number: int = Field(ge = 1, le= 99)
    position: Literal["GK", "DF", "MF", "FW"]
    nationality: str
    team_id: int

class PlayerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name : str
    shirt_number: int
    position: str
    nationality: str
    team_id: int

