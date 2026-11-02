import pytest

from app.sync.football_data import match_score


@pytest.fixture
def cup(make_league, make_team):
    """A cup competition with four teams."""
    league = make_league(name="Champions League", country="Europe")
    teams = {
        name: make_team(league["id"], name=name, short_name=name[:3].upper())
        for name in ("Arsenal", "Bayern", "PSG", "Inter")
    }
    return {"league": league, "teams": teams}


@pytest.fixture
def play(client, make_match, cup):
    """Play a finished knockout leg: play("SEMI_FINALS", "PSG", "Bayern", 2, 1)."""
    def _play(stage, home, away, home_score, away_score, kickoff="2027-04-01T19:00:00Z", pens=None, status="finished"):
        teams = cup["teams"]
        match = make_match(cup["league"]["id"], teams[home]["id"], teams[away]["id"], stage=stage, kickoff=kickoff)
        result = {"status": status, "home_score": home_score, "away_score": away_score}
        if pens:
            result |= {"home_penalties": pens[0], "away_penalties": pens[1]}
        return client.patch(f"/matches/{match['id']}", json=result).json()
    return _play


def get_bracket(client, cup_match):
    return client.get(f"/seasons/{cup_match['season_id']}/bracket").json()


def tie_in(bracket, round_):
    return next(r for r in bracket["rounds"] if r["round"] == round_)["ties"]


def test_two_legs_make_one_tie_with_an_aggregate(client, play, cup):
    play("SEMI_FINALS", "PSG", "Bayern", 2, 1, kickoff="2027-04-28T19:00:00Z")
    second = play("SEMI_FINALS", "Bayern", "PSG", 1, 1, kickoff="2027-05-05T19:00:00Z")

    (tie,) = tie_in(get_bracket(client, second), "SEMI_FINALS")

    assert tie["side_a"]["team_name"] == "PSG"  # home in the first leg
    assert len(tie["legs"]) == 2
    assert tie["aggregate"] == [3, 2]
    assert tie["winner_team_id"] == cup["teams"]["PSG"]["id"]


def test_level_aggregate_is_decided_on_penalties(client, play, cup):
    final = play("FINAL", "PSG", "Arsenal", 1, 1, pens=(4, 3))

    (tie,) = tie_in(get_bracket(client, final), "FINAL")

    assert tie["aggregate"] == [1, 1]
    assert tie["winner_team_id"] == cup["teams"]["PSG"]["id"]


def test_tie_has_no_winner_until_every_leg_is_finished(client, play):
    first = play("SEMI_FINALS", "PSG", "Bayern", 3, 0, kickoff="2027-04-28T19:00:00Z")
    play("SEMI_FINALS", "Bayern", "PSG", 0, 0, kickoff="2027-05-05T19:00:00Z", status="scheduled")

    (tie,) = tie_in(get_bracket(client, first), "SEMI_FINALS")

    assert tie["aggregate"] == [3, 0]
    assert tie["winner_team_id"] is None


def test_earlier_round_is_ordered_by_the_tie_it_feeds(client, play):
    play("SEMI_FINALS", "Arsenal", "Inter", 2, 0)  # listed first, but feeds the second half of the bracket
    play("SEMI_FINALS", "PSG", "Bayern", 2, 0)
    final = play("FINAL", "PSG", "Arsenal", 1, 0, kickoff="2027-05-30T19:00:00Z")

    semis = tie_in(get_bracket(client, final), "SEMI_FINALS")

    assert [t["side_a"]["team_name"] for t in semis] == ["PSG", "Arsenal"]


def test_knockout_matches_do_not_count_in_the_league_table(client, make_match, play, cup):
    league_id = cup["league"]["id"]
    league_game = make_match(league_id, cup["teams"]["PSG"]["id"], cup["teams"]["Inter"]["id"], stage="LEAGUE_STAGE")
    client.patch(f"/matches/{league_game['id']}", json={"status": "finished", "home_score": 1})
    play("FINAL", "Arsenal", "Bayern", 3, 0)

    table = {row["team_name"]: row for row in client.get(f"/leagues/{league_id}/standings").json()}

    assert table["PSG"]["points"] == 3
    assert "Arsenal" not in table  # only played in the knockouts


def test_projected_bracket_follows_uefa_seeding(client, make_league, make_team, make_season):
    league = make_league(name="Champions League", country="Europe")
    season = make_season(league["id"])
    for n in range(1, 37):  # with no games played the table is alphabetical: "Team 01" is 1st
        make_team(league["id"], name=f"Team {n:02}", short_name=f"T{n:02}")

    bracket = client.get(f"/seasons/{season['id']}/bracket/projected").json()
    playoffs, last_16 = tie_in(bracket, "PLAYOFFS"), tie_in(bracket, "LAST_16")

    assert bracket["projected"] is True
    assert (last_16[0]["side_a"]["label"], last_16[0]["side_b"]["label"]) == ("1st", "Winner of 16th v 17th")
    assert (playoffs[0]["side_a"]["team_name"], playoffs[0]["side_b"]["team_name"]) == ("Team 16", "Team 17")
    assert [t["side_a"]["label"] for t in last_16] == ["1st", "8th", "4th", "5th", "2nd", "7th", "3rd", "6th"]
    assert len(tie_in(bracket, "FINAL")) == 1


def test_projected_bracket_needs_24_teams(client, make_season, setup):
    season = make_season(setup["league"]["id"])

    assert client.get(f"/seasons/{season['id']}/bracket/projected").status_code == 409


def test_shootout_score_does_not_include_penalties():
    score = {"duration": "PENALTY_SHOOTOUT", "fullTime": {"home": 5, "away": 4},
             "regularTime": {"home": 1, "away": 1}, "extraTime": {"home": 0, "away": 0},
             "penalties": {"home": 4, "away": 3}}

    assert match_score(score) == (1, 1, 4, 3)
