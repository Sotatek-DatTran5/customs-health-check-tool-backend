"""Dashboard module tests."""
from tests.conftest import auth_header


def test_get_stats_super_admin(client, super_admin):
    r = client.get("/dashboard/stats", headers=auth_header(super_admin))
    assert r.status_code == 200
    data = r.json()
    assert "total_requests" in data
    assert "total_tenants" in data  # super admin gets tenant stats


def test_get_stats_admin(client, admin_user):
    r = client.get("/dashboard/stats", headers=auth_header(admin_user))
    assert r.status_code == 200
    data = r.json()
    assert "total_requests" in data
    assert data.get("total_tenants") is None  # tenant admin doesn't get this


def test_get_stats_normal_user_forbidden(client, normal_user):
    r = client.get("/dashboard/stats", headers=auth_header(normal_user))
    assert r.status_code == 403


def test_recent_tenants_super_admin(client, super_admin, tenant):
    r = client.get("/dashboard/recent-tenants", headers=auth_header(super_admin))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_recent_tenants_admin_forbidden(client, admin_user):
    r = client.get("/dashboard/recent-tenants", headers=auth_header(admin_user))
    assert r.status_code == 403


def test_recent_users(client, admin_user):
    r = client.get("/dashboard/recent-users", headers=auth_header(admin_user))
    assert r.status_code == 200


def test_recent_requests(client, admin_user):
    r = client.get("/dashboard/recent-requests", headers=auth_header(admin_user))
    assert r.status_code == 200


def test_role_distribution(client, super_admin):
    r = client.get("/dashboard/role-distribution", headers=auth_header(super_admin))
    assert r.status_code == 200
    data = r.json()
    assert "super_admin" in data
    assert "user" in data
