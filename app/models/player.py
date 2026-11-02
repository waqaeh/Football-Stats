from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class Player(Base):
    __tablename__ = "players"


    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=False)
    shirt_number: Mapped[int | None]
    nationality: Mapped[str] = mapped_column(String(100))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    position: Mapped[str | None] = mapped_column(String(2))
    # ID from football-data.org, used by the sync job. Empty for data added by hand.
    external_id: Mapped[int | None] = mapped_column(unique=True)
