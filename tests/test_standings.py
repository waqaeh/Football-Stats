def finish(client, make_match, league_id, home_id, away_id, home_score, away_score):
    match = make_match(league_id, home_id, away_id)
    client.patch(f"/matches/{match['id']}",
                 json={"status": "finished", "home_score": home_score, "away_score": away_score})


def test_empty_table_lists_every_team(client, setup):
    response = client.get(f"/leagues/{setup['league']['id']}/standings")

    assert response.status_code == 200
    assert {row["team_name"] for row in response.json()} == {"Arsenal", "Liverpool"}
    assert all(row["played"] == 0 and row["points"] == 0 for row in response.json())


def test_win_draw_and_loss_points(client, make_match, make_team, setup):
    league_id = setup["league"]["id"]
    ars, liv = setup["arsenal"]["id"], setup["liverpool"]["id"]
    finish(client, make_match, league_id, ars, liv, 2, 0)
    finish(client, make_match, league_id, liv, ars, 1, 1)

    table = {row["team_name"]: row for row in client.get(f"/leagues/{league_id}/standings").json()}

    assert (table["Arsenal"]["won"], table["Arsenal"]["drawn"], table["Arsenal"]["points"]) == (1, 1, 4)
    assert (table["Liverpool"]["lost"], table["Liverpool"]["drawn"], table["Liverpool"]["points"]) == (1, 1, 1)
    assert table["Arsenal"]["goal_difference"] == 2


def test_unfinished_matches_do_not_count(client, make_match, setup):
    league_id = setup["league"]["id"]
    match = make_match(league_id, setup["arsenal"]["id"], setup["liverpool"]["id"])
    client.patch(f"/matches/{match['id']}", json={"status": "live", "home_score": 3})

    table = client.get(f"/leagues/{league_id}/standings").json()

    assert all(row["played"] == 0 for row in table)


def test_tie_breaker_is_goal_difference_then_goals_scored(client, make_match, make_team, setup):
    league_id = setup["league"]["id"]
    ars, liv = setup["arsenal"]["id"], setup["liverpool"]["id"]
    che = make_team(league_id, name="Chelsea", short_name="CHE")["id"]
    whu = make_team(league_id, name="West Ham", short_name="WHU")["id"]
    finish(client, make_match, league_id, ars, whu, 1, 0)  # Arsenal: 3 pts, GD +1, GF 1
    finish(client, make_match, league_id, liv, che, 3, 2)  # Liverpool: 3 pts, GD +1, GF 3

    table = client.get(f"/leagues/{league_id}/standings").json()

    assert [row["team_name"] for row in table[:2]] == ["Liverpool", "Arsenal"]
    assert [row["position"] for row in table] == [1, 2, 3, 4]


def test_top_scorers_count_goals_and_assists(client, make_match, make_player, setup):
    league_id = setup["league"]["id"]
    saka = make_player(setup["arsenal"]["id"])
    rice = make_player(setup["arsenal"]["id"], name="Declan Rice", shirt_number=41, position="MF")
    salah = make_player(setup["liverpool"]["id"], name="Mo Salah", shirt_number=11)
    match = make_match(league_id, setup["arsenal"]["id"], setup["liverpool"]["id"], status="live")
    events = f"/matches/{match['id']}/events"
    client.post(events, json={"type": "goal", "minute": 10, "player_id": saka["id"], "related_player_id": rice["id"]})
    client.post(events, json={"type": "goal", "minute": 20, "player_id": saka["id"]})
    client.post(events, json={"type": "own_goal", "minute": 30, "player_id": salah["id"]})

    scorers = client.get(f"/leagues/{league_id}/top-scorers").json()

    assert [(s["player_name"], s["goals"]) for s in scorers] == [("Bukayo Saka", 2)]
    assert scorers[0]["assists"] == 0
