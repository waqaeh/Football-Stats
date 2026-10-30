def test_create_league(client):
    response = client.post("/leagues", json={"name": "Premier League", "country": "England"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Premier League"
    assert body["country"] == "England"
    assert "id" in body


def test_duplicate_league_is_rejected(client, make_league):
    make_league(name="La Liga", country="Spain")

    response = client.post("/leagues", json={"name": "La Liga", "country": "Spain"})

    assert response.status_code == 409


def test_missing_field_is_rejected(client):
    response = client.post("/leagues", json={"name": "Serie A"})

    assert response.status_code == 422


def test_list_leagues(client, make_league):
    make_league(name="Premier League")
    make_league(name="La Liga", country="Spain")

    response = client.get("/leagues")

    assert response.status_code == 200
    assert [league["name"] for league in response.json()] == ["Premier League", "La Liga"]


def test_get_unknown_league_returns_404(client):
    assert client.get("/leagues/999").status_code == 404
