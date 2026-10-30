def valid_player(team_id, **changes):
    """A valid player request. Pass changes to break exactly one thing."""
    player = {
        "name": "Bukayo Saka",
        "shirt_number": 7,
        "position": "FW",
        "nationality": "England",
        "team_id": team_id,
    }
    player.update(changes)
    return player


def test_create_player(client, make_league, make_team):
    league = make_league()
    team = make_team(league["id"])

    response = client.post("/players", json=valid_player(team["id"]))

    assert response.status_code == 201
    assert response.json()["team_id"] == team["id"]


def test_shirt_number_above_99_is_rejected(client, make_league, make_team):
    league = make_league()
    team = make_team(league["id"])

    response = client.post("/players", json=valid_player(team["id"], shirt_number=100))

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "shirt_number"]


def test_invalid_position_is_rejected(client, make_league, make_team):
    league = make_league()
    team = make_team(league["id"])

    response = client.post("/players", json=valid_player(team["id"], position="ST"))

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "position"]


def test_player_on_unknown_team_is_rejected(client):
    response = client.post("/players", json=valid_player(team_id=999))

    assert response.status_code == 404


def test_team_players_only_lists_that_team(client, make_league, make_team, make_player):
    league = make_league()
    arsenal = make_team(league["id"])
    liverpool = make_team(league["id"], name="Liverpool", short_name="LIV")
    make_player(arsenal["id"])
    make_player(liverpool["id"], name="Mo Salah", shirt_number=11)

    response = client.get(f"/teams/{arsenal['id']}/players")

    assert [player["name"] for player in response.json()] == ["Bukayo Saka"]


def test_bulk_create_adds_every_player(client, make_league, make_team):
    league = make_league()
    team = make_team(league["id"])

    response = client.post(
        "/players/bulk",
        json=[valid_player(team["id"]), valid_player(team["id"], name="Declan Rice", shirt_number=41)],
    )

    assert response.status_code == 201
    assert len(client.get("/players").json()) == 2


def test_bulk_create_is_all_or_nothing(client, make_league, make_team):
    league = make_league()
    team = make_team(league["id"])

    response = client.post(
        "/players/bulk",
        json=[valid_player(team["id"]), valid_player(team_id=999, name="Nobody")],
    )

    assert response.status_code == 404
    assert client.get("/players").json() == []
