from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prediction(Base):
    """A user's pick for who wins a knockout tie. The tie is identified by season, round and its two teams."""

    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "season_id", "round", "team_a_id", "team_b_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id"))
    round: Mapped[str] = mapped_column(String(30))
    # Stored lowest id first, so a tie has one key whichever team was at home first.
    team_a_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    team_b_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    winner_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
