from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    short_name: Mapped[str] = mapped_column(String(3))
    stadium: Mapped[str | None] = mapped_column(String(100))
    crest_url: Mapped[str | None] = mapped_column(String(300))
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    # ID from football-data.org, used by the sync job. Empty for data added by hand.
    external_id: Mapped[int | None] = mapped_column(unique=True)
