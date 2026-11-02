import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"


# football-data.org's names for knockout rounds, in order.
KNOCKOUT_ROUNDS = ["PLAYOFFS", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    kickoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[MatchStatus] = mapped_column(default=MatchStatus.SCHEDULED)
    home_score: Mapped[int] = mapped_column(default=0)
    away_score: Mapped[int] = mapped_column(default=0)
    # Only set when a knockout match goes to a penalty shootout.
    home_penalties: Mapped[int | None]
    away_penalties: Mapped[int | None]
    # e.g. "REGULAR_SEASON", "LEAGUE_STAGE", or a knockout round like "LAST_16"
    stage: Mapped[str | None] = mapped_column(String(30))
    # ID from football-data.org, used by the sync job. Empty for data added by hand.
    external_id: Mapped[int | None] = mapped_column(unique=True)
