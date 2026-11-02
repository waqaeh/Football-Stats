from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator


class SeasonCreate(BaseModel):
    name: str
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class SeasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    name: str
    start_date: date
    end_date: date
