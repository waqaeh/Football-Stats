from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EventType, Match, MatchEvent, Player, Team


def top_scorers(league_id: int, db: Session, limit: int) -> list[dict]:
    goals = func.count(MatchEvent.id).label("goals")
    rows = db.execute(
        select(Player.id, Player.name, Team.id, Team.name, goals)
        .join(MatchEvent, MatchEvent.player_id == Player.id)
        .join(Match, Match.id == MatchEvent.match_id)
        .join(Team, Team.id == MatchEvent.team_id)
        .where(Match.league_id == league_id, MatchEvent.type == EventType.GOAL)
        .group_by(Player.id, Player.name, Team.id, Team.name)
        .order_by(goals.desc(), Player.name)
        .limit(limit)
    ).all()

    assists = dict(
        db.execute(
            select(MatchEvent.related_player_id, func.count(MatchEvent.id))
            .join(Match, Match.id == MatchEvent.match_id)
            .where(
                Match.league_id == league_id,
                MatchEvent.type == EventType.GOAL,
                MatchEvent.related_player_id.is_not(None),
            )
            .group_by(MatchEvent.related_player_id)
        ).all()
    )

    return [
        {
            "player_id": player_id,
            "player_name": player_name,
            "team_id": team_id,
            "team_name": team_name,
            "goals": goal_count,
            "assists": assists.get(player_id, 0),
        }
        for player_id, player_name, team_id, team_name, goal_count in rows
    ]
