from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    # Name constraints the way Postgres does by default, so migrations can refer to them.
    metadata = MetaData(naming_convention={
        "pk": "%(table_name)s_pkey",
        "uq": "%(table_name)s_%(column_0_name)s_key",
        "fk": "%(table_name)s_%(column_0_name)s_fkey",
    })


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
