from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import auth, leagues, match_events, matches, players, predictions, seasons, teams

app = FastAPI(title="Football Stats API")
app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(match_events.router)
app.include_router(seasons.router)
app.include_router(auth.router)
app.include_router(predictions.router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
