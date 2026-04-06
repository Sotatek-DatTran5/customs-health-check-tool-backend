"""Auth module tests: login, brute-force, refresh, change/reset password."""
from tests.conftest import auth_header


# --- Login ---

def test_login_success(client, normal_user):
    r = client.post("/auth/login", json={"email": "user@test.com", "password": "User@1234"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, normal_user):
    r = client.post("/auth/login", json={"email": "user@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    r = client.post("/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_user(client, db, normal_user):
    normal_user.is_active = False
    db.flush()
    r = client.post("/auth/login", json={"email": "user@test.com", "password": "User@1234"})
    assert r.status_code == 401  # inactive user filtered by repository query


# --- Brute force ---

def test_brute_force_lockout(client, normal_user):
    for _ in range(5):
        client.post("/auth/login", json={"email": "user@test.com", "password": "wrong"})
    r = client.post("/auth/login", json={"email": "user@test.com", "password": "User@1234"})
    assert r.status_code == 423


# --- Refresh ---

def test_refresh_token(client, normal_user):
    login_r = client.post("/auth/login", json={"email": "user@test.com", "password": "User@1234"})
    refresh = login_r.json()["refresh_token"]
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_with_access_token_fails(client, normal_user):
    login_r = client.post("/auth/login", json={"email": "user@test.com", "password": "User@1234"})
    access = login_r.json()["access_token"]
    r = client.post("/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401


def test_refresh_invalid_token(client):
    r = client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401


# --- Logout ---

def test_logout(client, normal_user):
    headers = auth_header(normal_user)
    r = client.post("/auth/logout", headers=headers)
    assert r.status_code == 200


# --- Change password ---

def test_change_password_success(client, normal_user):
    headers = auth_header(normal_user)
    r = client.post("/auth/change-password", headers=headers, json={
        "current_password": "User@1234",
        "new_password": "NewPass@1",
        "confirm_new_password": "NewPass@1",
    })
    assert r.status_code == 200


def test_change_password_wrong_current(client, normal_user):
    headers = auth_header(normal_user)
    r = client.post("/auth/change-password", headers=headers, json={
        "current_password": "wrong",
        "new_password": "NewPass@1",
        "confirm_new_password": "NewPass@1",
    })
    assert r.status_code == 400


def test_change_password_mismatch(client, normal_user):
    headers = auth_header(normal_user)
    r = client.post("/auth/change-password", headers=headers, json={
        "current_password": "User@1234",
        "new_password": "NewPass@1",
        "confirm_new_password": "Different@1",
    })
    assert r.status_code == 400


def test_change_password_weak(client, normal_user):
    headers = auth_header(normal_user)
    r = client.post("/auth/change-password", headers=headers, json={
        "current_password": "User@1234",
        "new_password": "short",
        "confirm_new_password": "short",
    })
    assert r.status_code == 400


# --- Unauthenticated access ---

def test_protected_route_no_token(client):
    r = client.post("/auth/logout")
    assert r.status_code in (401, 403)  # HTTPBearer behavior varies
