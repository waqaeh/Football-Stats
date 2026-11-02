"""Champions League knockout brackets.

The real bracket is built from knockout matches: the legs between the same two teams in the same round form a tie.
The projected bracket shows who would meet if the league phase ended today.
"""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KNOCKOUT_ROUNDS, Match, MatchStatus
from app.services.standings import TeamRecord

@dataclass
class Side:
    team_id: int | None = None
    team_name: str | None = None
    label: str | None = None  # for a projected tie, e.g. "1st" or "Winner of play-off 8"


@dataclass
class Tie:
    round: str
    side_a: Side
    side_b: Side
    legs: list[Match] = field(default_factory=list)

    def _goals(self, team_id: int) -> int:
        return sum(
            leg.home_score if leg.home_team_id == team_id else leg.away_score
            for leg in self.legs
            if leg.status in (MatchStatus.LIVE, MatchStatus.FINISHED)
        )

    @property
    def aggregate(self) -> tuple[int, int] | None:
        if not any(leg.status in (MatchStatus.LIVE, MatchStatus.FINISHED) for leg in self.legs):
            return None
        return self._goals(self.side_a.team_id), self._goals(self.side_b.team_id)

    @property
    def winner_team_id(self) -> int | None:
        if not self.legs or any(leg.status != MatchStatus.FINISHED for leg in self.legs):
            return None
        a, b = self.aggregate
        if a != b:
            return self.side_a.team_id if a > b else self.side_b.team_id
        last = self.legs[-1]  # level on aggregate: decided by the last leg's shootout
        if last.home_penalties is None or last.away_penalties is None:
            return None
        return last.home_team_id if last.home_penalties > last.away_penalties else last.away_team_id

    def has_team(self, team_id: int | None) -> bool:
        return team_id is not None and team_id in (self.side_a.team_id, self.side_b.team_id)


def real_bracket(season_id: int, db: Session, team_names: dict[int, str]) -> dict[str, list[Tie]]:
    matches = db.scalars(
        select(Match)
        .where(Match.season_id == season_id, Match.stage.in_(KNOCKOUT_ROUNDS))
        .order_by(Match.kickoff, Match.id)
    ).all()

    ties: dict[tuple, Tie] = {}
    for match in matches:
        key = (match.stage, frozenset((match.home_team_id, match.away_team_id)))
        if key not in ties:  # the first leg's home team is side A
            ties[key] = Tie(
                round=match.stage,
                side_a=Side(match.home_team_id, team_names[match.home_team_id]),
                side_b=Side(match.away_team_id, team_names[match.away_team_id]),
            )
        ties[key].legs.append(match)

    by_round = {round_: [t for t in ties.values() if t.round == round_] for round_ in KNOCKOUT_ROUNDS}
    return order_like_a_bracket(by_round)


def order_like_a_bracket(by_round: dict[str, list[Tie]]) -> dict[str, list[Tie]]:
    """Put each round in bracket order: the ties feeding a later tie sit next to each other."""
    for i in range(len(KNOCKOUT_ROUNDS) - 2, -1, -1):
        later, earlier = by_round[KNOCKOUT_ROUNDS[i + 1]], by_round[KNOCKOUT_ROUNDS[i]]
        ordered = []
        for later_tie in later:
            for side in (later_tie.side_a, later_tie.side_b):
                ordered += [t for t in earlier if t.has_team(side.team_id) and t not in ordered]
        by_round[KNOCKOUT_ROUNDS[i]] = ordered + [t for t in earlier if t not in ordered]
    return by_round


# Seeds that meet in the round of 16, listed in bracket order so that 1st and 2nd can only meet in the final.
R16_SEED_ORDER = [1, 8, 4, 5, 2, 7, 3, 6]


def ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def projected_bracket(table: list[TeamRecord]) -> dict[str, list[Tie]]:
    """The bracket if the league phase ended now, following UEFA's seeding pattern.

    UEFA draws between pairs of seeds (e.g. 1st or 2nd face the winner of 15th/16th v 17th/18th);
    this picks one fixed outcome of that draw so the bracket can be shown before it happens.
    """
    def seeded(position: int) -> Side:
        record = table[position - 1]
        return Side(record.team_id, record.team_name, ordinal(position))

    # Play-offs: 9th v 24th, 10th v 23rd, ... 16th v 17th.
    playoffs = {seed: Tie("PLAYOFFS", seeded(seed), seeded(33 - seed)) for seed in range(9, 17)}

    # Round of 16: seed n (1-8) faces the winner of the play-off involving seed 17 - n.
    last_16 = []
    for n in R16_SEED_ORDER:
        playoff = playoffs[17 - n]
        feeder = f"Winner of {playoff.side_a.label} v {playoff.side_b.label}"
        last_16.append(Tie("LAST_16", seeded(n), Side(label=feeder)))

    by_round = {"PLAYOFFS": [], "LAST_16": last_16}
    previous = last_16
    for round_, name in [("QUARTER_FINALS", "QF"), ("SEMI_FINALS", "SF"), ("FINAL", "Final")]:
        short = {"LAST_16": "R16", "QUARTER_FINALS": "QF", "SEMI_FINALS": "SF"}[previous[0].round]
        by_round[round_] = [
            Tie(round_, Side(label=f"Winner of {short} {2 * i + 1}"), Side(label=f"Winner of {short} {2 * i + 2}"))
            for i in range(len(previous) // 2)
        ]
        previous = by_round[round_]

    # List play-offs in the same order as the round of 16 ties they feed.
    by_round["PLAYOFFS"] = [playoffs[17 - n] for n in R16_SEED_ORDER]
    return by_round
