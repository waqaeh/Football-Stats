from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import auth, leagues, match_events, matches, players, predictions, rules, seasons, teams

app = FastAPI(title="Football Stats API")
app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(match_events.router)
app.include_router(seasons.router)
app.include_router(auth.router)
app.include_router(predictions.router)
app.include_router(rules.router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


# The website. Mounted last, so every API route above takes priority over a file with the same path.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="website")
