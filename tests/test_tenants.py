"""Tenants module tests: CRUD, expert management."""
from unittest.mock import patch

from tests.conftest import auth_header


# --- List tenants ---

def test_list_tenants_super_admin(client, super_admin, tenant):
    r = client.get("/tenants", headers=auth_header(super_admin))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_tenants_normal_user_forbidden(client, normal_user):
    r = client.get("/tenants", headers=auth_header(normal_user))
    assert r.status_code == 403


# --- Create tenant ---

@patch("app.tenants.service.send_welcome_email")
def test_create_tenant(mock_email, client, super_admin):
    r = client.post("/tenants", headers=auth_header(super_admin), json={
        "name": "New Tenant",
        "tenant_code": "NEWTNT",
        "admin_email": "admin@newtnt.com",
        "admin_full_name": "New Admin",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_code"] == "NEWTNT"
    assert data["subdomain"] == "newtnt"
    mock_email.assert_called_once()


@patch("app.tenants.service.send_welcome_email")
def test_create_tenant_duplicate_code(mock_email, client, super_admin, tenant):
    r = client.post("/tenants", headers=auth_header(super_admin), json={
        "name": "Dup Tenant",
        "tenant_code": "TEST",
        "admin_email": "admin2@test.com",
        "admin_full_name": "Dup Admin",
    })
    assert r.status_code == 400


# --- Get / Update / Delete tenant ---

def test_get_tenant(client, super_admin, tenant):
    r = client.get(f"/tenants/{tenant.id}", headers=auth_header(super_admin))
    assert r.status_code == 200
    assert r.json()["name"] == "Test Corp"


def test_update_tenant(client, super_admin, tenant):
    r = client.put(f"/tenants/{tenant.id}", headers=auth_header(super_admin), json={
        "name": "Updated Corp",
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Corp"


def test_delete_tenant(client, super_admin, tenant):
    r = client.delete(f"/tenants/{tenant.id}", headers=auth_header(super_admin))
    assert r.status_code == 200


# --- Expert management ---

@patch("app.tenants.service.send_welcome_email")
def test_create_expert(mock_email, client, super_admin):
    r = client.post("/tenants/experts", headers=auth_header(super_admin), json={
        "email": "newexpert@chc.com",
        "full_name": "New Expert",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "newexpert@chc.com"
    mock_email.assert_called_once()


def test_list_experts(client, super_admin, expert_user):
    r = client.get("/tenants/experts/all", headers=auth_header(super_admin))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
