from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    short_name: Mapped[str] = mapped_column(String(3))
    stadium: Mapped[str] = mapped_column(String(100))
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
