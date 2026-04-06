"""Users module tests: CRUD, onboarding, locale."""
from unittest.mock import patch

from tests.conftest import auth_header


# --- List users ---

def test_list_users_as_admin(client, admin_user, normal_user):
    r = client.get("/users", headers=auth_header(admin_user))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_users_as_normal_user_forbidden(client, normal_user):
    r = client.get("/users", headers=auth_header(normal_user))
    assert r.status_code == 403


# --- Create user ---

@patch("app.users.service.send_welcome_email")
def test_create_user(mock_email, client, admin_user):
    r = client.post("/users", headers=auth_header(admin_user), json={
        "email": "newuser@test.com",
        "full_name": "New User",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "user"
    mock_email.assert_called_once()


@patch("app.users.service.send_welcome_email")
def test_create_user_duplicate_email(mock_email, client, admin_user, normal_user):
    r = client.post("/users", headers=auth_header(admin_user), json={
        "email": "user@test.com",
        "full_name": "Dup User",
    })
    assert r.status_code == 400


# --- Update user ---

def test_update_user(client, admin_user, normal_user):
    r = client.put(f"/users/{normal_user.id}", headers=auth_header(admin_user), json={
        "full_name": "Updated Name",
    })
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated Name"


# --- Delete user ---

def test_delete_user(client, admin_user, normal_user):
    r = client.delete(f"/users/{normal_user.id}", headers=auth_header(admin_user))
    assert r.status_code == 200


# --- Onboarding ---

def test_onboarding(client, normal_user):
    r = client.post("/users/onboarding", headers=auth_header(normal_user), json={
        "company_name": "ACME Corp",
        "tax_code": "0123456789",
        "company_address": "123 Main St",
        "contact_person": "John",
        "phone": "0901234567",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["company_name"] == "ACME Corp"
    assert data["is_first_login"] is False


# --- Locale ---

def test_update_locale(client, normal_user):
    r = client.put("/users/locale", headers=auth_header(normal_user), json={"locale": "en"})
    assert r.status_code == 200
    assert r.json()["locale"] == "en"


def test_update_locale_invalid(client, normal_user):
    r = client.put("/users/locale", headers=auth_header(normal_user), json={"locale": "fr"})
    assert r.status_code == 400
