import pytest


@pytest.fixture
def live_match(make_player, make_match, setup):
    """Arsenal (Saka, Rice) vs Liverpool (Salah), already kicked off."""
    return {
        "match": make_match(setup["league"]["id"], setup["arsenal"]["id"], setup["liverpool"]["id"], status="live"),
        "saka": make_player(setup["arsenal"]["id"]),
        "rice": make_player(setup["arsenal"]["id"], name="Declan Rice", shirt_number=41, position="MF"),
        "salah": make_player(setup["liverpool"]["id"], name="Mo Salah", shirt_number=11),
    }


def add_event(client, match_id, **event):
    return client.post(f"/matches/{match_id}/events", json=event)


def score(client, match_id):
    match = client.get(f"/matches/{match_id}").json()
    return match["home_score"], match["away_score"]


def test_goal_updates_score(client, live_match):
    match_id = live_match["match"]["id"]

    response = add_event(client, match_id, type="goal", minute=34, player_id=live_match["saka"]["id"])

    assert response.status_code == 201
    assert response.json()["team_id"] == live_match["saka"]["team_id"]
    assert score(client, match_id) == (1, 0)


def test_own_goal_counts_for_the_other_team(client, live_match):
    match_id = live_match["match"]["id"]

    add_event(client, match_id, type="own_goal", minute=50, player_id=live_match["salah"]["id"])

    assert score(client, match_id) == (1, 0)


def test_cards_do_not_change_score(client, live_match):
    match_id = live_match["match"]["id"]

    add_event(client, match_id, type="yellow_card", minute=20, player_id=live_match["salah"]["id"])

    assert score(client, match_id) == (0, 0)


def test_deleting_a_goal_reverts_score(client, live_match):
    match_id = live_match["match"]["id"]
    goal = add_event(client, match_id, type="goal", minute=88, player_id=live_match["saka"]["id"]).json()

    response = client.delete(f"/matches/{match_id}/events/{goal['id']}")

    assert response.status_code == 204
    assert score(client, match_id) == (0, 0)


def test_no_events_before_kickoff(client, make_match, make_player, setup):
    match = make_match(setup["league"]["id"], setup["arsenal"]["id"], setup["liverpool"]["id"])
    saka = make_player(setup["arsenal"]["id"])

    response = add_event(client, match["id"], type="goal", minute=5, player_id=saka["id"])

    assert response.status_code == 409


def test_player_from_another_team_is_rejected(client, live_match, make_team, make_player, setup):
    barcelona = make_team(setup["league"]["id"], name="Barcelona", short_name="BAR")
    yamal = make_player(barcelona["id"], name="Lamine Yamal", shirt_number=19)

    response = add_event(client, live_match["match"]["id"], type="goal", minute=90, player_id=yamal["id"])

    assert response.status_code == 422


def test_assist_must_be_a_teammate(client, live_match):
    response = add_event(
        client, live_match["match"]["id"], type="goal", minute=10,
        player_id=live_match["saka"]["id"], related_player_id=live_match["salah"]["id"],
    )

    assert response.status_code == 422


def test_substitution_needs_incoming_player(client, live_match):
    response = add_event(client, live_match["match"]["id"], type="substitution", minute=70,
                         player_id=live_match["saka"]["id"])

    assert response.status_code == 422


def test_timeline_is_sorted_by_minute(client, live_match):
    match_id = live_match["match"]["id"]
    add_event(client, match_id, type="goal", minute=80, player_id=live_match["saka"]["id"])
    add_event(client, match_id, type="yellow_card", minute=12, player_id=live_match["salah"]["id"])

    response = client.get(f"/matches/{match_id}/events")

    assert [event["minute"] for event in response.json()] == [12, 80]
