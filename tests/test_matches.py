def test_new_match_is_scheduled_at_nil_nil(make_match, setup):
    match = make_match(setup["league"]["id"], setup["arsenal"]["id"], setup["liverpool"]["id"])

    assert match["status"] == "scheduled"
    assert (match["home_score"], match["away_score"]) == (0, 0)


def test_team_cannot_play_itself(client, setup):
    arsenal_id = setup["arsenal"]["id"]

    response = client.post(
        "/matches",
        json={"league_id": setup["league"]["id"], "home_team_id": arsenal_id,
              "away_team_id": arsenal_id, "kickoff": "2026-11-01T15:00:00Z"},
    )

    assert response.status_code == 422


def test_patch_only_changes_fields_sent(client, make_match, setup):
    match = make_match(setup["league"]["id"], setup["arsenal"]["id"], setup["liverpool"]["id"])
    client.patch(f"/matches/{match['id']}", json={"home_score": 2})

    response = client.patch(f"/matches/{match['id']}", json={"status": "live"})

    assert response.json()["status"] == "live"
    assert response.json()["home_score"] == 2


def test_filter_matches_by_team_and_status(client, make_team, make_match, setup):
    league_id = setup["league"]["id"]
    chelsea = make_team(league_id, name="Chelsea", short_name="CHE")
    finished = make_match(league_id, setup["arsenal"]["id"], setup["liverpool"]["id"], status="finished")
    make_match(league_id, chelsea["id"], setup["arsenal"]["id"])  # Arsenal, but still scheduled
    make_match(league_id, setup["liverpool"]["id"], chelsea["id"], status="finished")  # finished, no Arsenal

    response = client.get("/matches", params={"team_id": setup["arsenal"]["id"], "status": "finished"})

    assert [m["id"] for m in response.json()] == [finished["id"]]
