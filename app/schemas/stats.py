from pydantic import BaseModel


class StandingRow(BaseModel):
    position: int
    team_id: int
    team_name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class TopScorer(BaseModel):
    player_id: int
    player_name: str
    team_id: int
    team_name: str
    goals: int
    assists: int
