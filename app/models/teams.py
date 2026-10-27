from sqlalchemy import ForeignKey
league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))


