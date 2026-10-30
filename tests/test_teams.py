def test_create_team(client, make_league):
    league = make_league()

    response = client.post(
        "/teams",
        json={"name": "Arsenal", "short_name": "ARS", "stadium": "Emirates Stadium", "league_id": league["id"]},
    )

    assert response.status_code == 201
    assert response.json()["league_id"] == league["id"]


def test_team_in_unknown_league_is_rejected(client):
    response = client.post(
        "/teams", json={"name": "Arsenal", "short_name": "ARS", "stadium": "Emirates", "league_id": 999}
    )

    assert response.status_code == 404


def test_short_name_must_be_three_letters(client, make_league):
    league = make_league()

    response = client.post(
        "/teams", json={"name": "Arsenal", "short_name": "ARSENAL", "stadium": "Emirates", "league_id": league["id"]}
    )

    assert response.status_code == 422


def test_league_teams_only_lists_that_league(client, make_league, make_team):
    premier = make_league()
    la_liga = make_league(name="La Liga", country="Spain")
    make_team(premier["id"])
    make_team(la_liga["id"], name="Barcelona", short_name="BAR")

    response = client.get(f"/leagues/{premier['id']}/teams")

    assert [team["name"] for team in response.json()] == ["Arsenal"]
