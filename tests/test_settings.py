"""Settings module tests: profile, email config."""
from tests.conftest import auth_header


def test_get_profile(client, normal_user):
    r = client.get("/settings/profile", headers=auth_header(normal_user))
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "user@test.com"
    assert data["full_name"] == "Test User"


def test_update_profile(client, db, normal_user):
    r = client.put("/settings/profile", headers=auth_header(normal_user), json={
        "full_name": "Updated User",
        "phone": "0909999999",
    })
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated User"


def test_get_profile_unauthenticated(client):
    r = client.get("/settings/profile")
    assert r.status_code in (401, 403)
