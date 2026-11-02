import pytest

FUTURE = "2099-03-01T20:00:00Z"


@pytest.fixture
def cup(client, make_league, make_team, make_match):
    """A Champions League final between PSG and Arsenal, not played yet."""
    league = make_league(name="Champions League", country="Europe")
    psg = make_team(league["id"], name="PSG", short_name="PSG")
    arsenal = make_team(league["id"], name="Arsenal", short_name="ARS")
    final = make_match(league["id"], psg["id"], arsenal["id"], stage="FINAL", kickoff=FUTURE)
    return {"season_id": final["season_id"], "psg": psg["id"], "arsenal": arsenal["id"], "final": final}


def pick(cup, winner, round_="FINAL"):
    return {"round": round_, "team_a_id": cup["psg"], "team_b_id": cup["arsenal"], "winner_team_id": cup[winner]}


def predict(client, cup, headers, winner, round_="FINAL"):
    return client.put(f"/seasons/{cup['season_id']}/predictions", json=pick(cup, winner, round_), headers=headers)


def finish_final(client, cup, home_score, away_score):
    client.patch(f"/matches/{cup['final']['id']}",
                 json={"status": "finished", "home_score": home_score, "away_score": away_score})


def test_predicting_needs_login(client, cup):
    response = client.put(f"/seasons/{cup['season_id']}/predictions", json=pick(cup, "psg"))

    assert response.status_code == 401


def test_predict_a_tie(client, cup, login):
    response = predict(client, cup, login(), "arsenal")

    assert response.status_code == 200
    assert response.json()["winner_team_id"] == cup["arsenal"]
    assert response.json()["correct"] is None


def test_changing_a_pick_replaces_it(client, cup, login):
    headers = login()
    predict(client, cup, headers, "arsenal")

    predict(client, cup, headers, "psg")

    mine = client.get(f"/seasons/{cup['season_id']}/predictions/me", headers=headers).json()
    assert [p["winner_team_id"] for p in mine] == [cup["psg"]]


def test_team_order_does_not_matter(client, cup, login):
    swapped = {"round": "FINAL", "team_a_id": cup["arsenal"], "team_b_id": cup["psg"], "winner_team_id": cup["psg"]}

    response = client.put(f"/seasons/{cup['season_id']}/predictions", json=swapped, headers=login())

    assert response.status_code == 200


def test_unknown_tie_is_rejected(client, cup, login):
    assert predict(client, cup, login(), "psg", round_="SEMI_FINALS").status_code == 404


def test_winner_must_be_in_the_tie(client, cup, login):
    bad = pick(cup, "psg") | {"winner_team_id": 999999}

    response = client.put(f"/seasons/{cup['season_id']}/predictions", json=bad, headers=login())

    assert response.status_code == 422


def test_invalid_round_is_rejected(client, cup, login):
    assert predict(client, cup, login(), "psg", round_="GROUP_OF_DEATH").status_code == 422


def test_no_picks_after_kickoff(client, cup, login):
    client.patch(f"/matches/{cup['final']['id']}", json={"status": "live"})

    assert predict(client, cup, login(), "psg").status_code == 409


def test_correct_pick_scores_round_points(client, cup, login):
    headers = login()
    predict(client, cup, headers, "psg")
    finish_final(client, cup, 2, 0)

    (mine,) = client.get(f"/seasons/{cup['season_id']}/predictions/me", headers=headers).json()

    assert (mine["correct"], mine["points"]) == (True, 16)


def test_leaderboard_ranks_by_points(client, cup, login):
    predict(client, cup, login("ameer"), "psg")
    predict(client, cup, login("rival"), "arsenal")
    finish_final(client, cup, 2, 0)

    board = client.get(f"/seasons/{cup['season_id']}/predictions/leaderboard").json()

    assert [(row["username"], row["points"]) for row in board] == [("ameer", 16), ("rival", 0)]
    assert board[0]["position"] == 1


def test_you_only_see_your_own_predictions(client, cup, login):
    predict(client, cup, login("ameer"), "psg")

    mine = client.get(f"/seasons/{cup['season_id']}/predictions/me", headers=login("rival")).json()

    assert mine == []
