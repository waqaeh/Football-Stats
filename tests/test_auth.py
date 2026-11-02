from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def test_register(client):
    response = client.post("/auth/register", json={"username": "ameer", "password": "correct-horse"})

    assert response.status_code == 201
    assert response.json() == {"id": response.json()["id"], "username": "ameer"}  # no password in the response


def test_password_is_stored_hashed(client, db):
    from app.models import User

    client.post("/auth/register", json={"username": "ameer", "password": "correct-horse"})

    stored = db.query(User).one().password_hash
    assert "correct-horse" not in stored
    assert stored.startswith("$2b$")  # bcrypt


def test_username_must_be_unique(client):
    client.post("/auth/register", json={"username": "ameer", "password": "correct-horse"})

    response = client.post("/auth/register", json={"username": "ameer", "password": "another-one"})

    assert response.status_code == 409


def test_short_password_is_rejected(client):
    response = client.post("/auth/register", json={"username": "ameer", "password": "short"})

    assert response.status_code == 422


def test_login_and_get_me(client, login):
    headers = login("ameer")

    response = client.get("/auth/me", headers=headers)

    assert response.json()["username"] == "ameer"


def test_wrong_password_is_rejected(client):
    client.post("/auth/register", json={"username": "ameer", "password": "correct-horse"})

    response = client.post("/auth/login", data={"username": "ameer", "password": "wrong-horse"})

    assert response.status_code == 401


def test_me_needs_a_token(client):
    assert client.get("/auth/me").status_code == 401


def test_forged_token_is_rejected(client, login):
    login("ameer")
    forged = jwt.encode({"sub": "1"}, "not-the-real-secret", algorithm="HS256")

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_expired_token_is_rejected(client, login):
    user_id = client.get("/auth/me", headers=login("ameer")).json()["id"]
    expired = jwt.encode({"sub": str(user_id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         settings.jwt_secret, algorithm="HS256")

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
