from datetime import date

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("league_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    name: Mapped[str] = mapped_column(String(20))  # e.g. "2026/27"
    start_date: Mapped[date]
    end_date: Mapped[date]
    # ID from football-data.org, used by the sync job. Empty for data added by hand.
    external_id: Mapped[int | None] = mapped_column(unique=True)
