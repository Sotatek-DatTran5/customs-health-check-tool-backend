"""Requests module tests: CHC, E-Tariff, assign, upload, approve, cancel."""
import io
from unittest.mock import patch

from app.models.request import RequestStatus, RequestType
from app.requests import repository as req_repo
from tests.conftest import auth_header


def _make_excel_file(filename="test.xlsx"):
    """Create a minimal .xlsx file (openpyxl)."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["col1", "col2"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return (filename, buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- Create CHC request ---

@patch("app.requests.service.send_request_confirmation")
@patch("app.requests.service._notify_admins_new_request")
@patch("app.core.storage.upload_file", return_value="fake-key")
def test_create_chc_request(mock_s3, mock_notify, mock_confirm, client, normal_user):
    file_tuple = _make_excel_file()
    r = client.post(
        "/requests/chc",
        headers=auth_header(normal_user),
        files=[("files", file_tuple)],
        data={"chc_modules": ["tariff_classification"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "chc"
    assert data["status"] == "pending"
    assert "tariff_classification" in data["chc_modules"]


@patch("app.requests.service.send_request_confirmation")
@patch("app.requests.service._notify_admins_new_request")
@patch("app.core.storage.upload_file", return_value="fake-key")
def test_create_chc_invalid_file_type(mock_s3, mock_notify, mock_confirm, client, normal_user):
    r = client.post(
        "/requests/chc",
        headers=auth_header(normal_user),
        files=[("files", ("test.pdf", io.BytesIO(b"fake"), "application/pdf"))],
        data={"chc_modules": ["tariff_classification"]},
    )
    assert r.status_code == 400


# --- Create E-Tariff manual ---

@patch("app.requests.service.send_request_confirmation")
@patch("app.core.storage.upload_file", return_value="fake-key")
def test_create_etariff_manual(mock_s3, mock_confirm, client, normal_user):
    r = client.post(
        "/requests/etariff/manual",
        headers=auth_header(normal_user),
        json={
            "commodity_name": "Steel Rod",
            "description": "Carbon steel rod 10mm",
            "function": "Construction",
            "material_composition": "Carbon steel",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "etariff_manual"


# --- Create E-Tariff batch ---

@patch("app.requests.service.send_request_confirmation")
@patch("app.core.storage.upload_file", return_value="fake-key")
def test_create_etariff_batch(mock_s3, mock_confirm, client, normal_user):
    file_tuple = _make_excel_file()
    r = client.post(
        "/requests/etariff/batch",
        headers=auth_header(normal_user),
        files=[("files", file_tuple)],
    )
    assert r.status_code == 200
    assert r.json()["type"] == "etariff_batch"


# --- List my requests ---

def test_list_my_requests(client, normal_user):
    r = client.get("/requests/my", headers=auth_header(normal_user))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# --- Cancel request ---

@patch("app.requests.service.send_request_confirmation")
@patch("app.requests.service._notify_admins_new_request")
@patch("app.requests.service.send_cancel_notification")
@patch("app.core.storage.upload_file", return_value="fake-key")
def test_cancel_request(mock_s3, mock_cancel, mock_notify, mock_confirm, client, normal_user):
    # Create a request first
    file_tuple = _make_excel_file()
    create_r = client.post(
        "/requests/chc",
        headers=auth_header(normal_user),
        files=[("files", file_tuple)],
        data={"chc_modules": ["tariff_classification"]},
    )
    req_id = create_r.json()["id"]

    r = client.post(
        f"/requests/my/{req_id}/cancel",
        headers=auth_header(normal_user),
        json={"reason": "Changed my mind"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


# --- Admin list requests ---

def test_admin_list_requests(client, admin_user):
    r = client.get("/requests", headers=auth_header(admin_user))
    assert r.status_code == 200


def test_super_admin_list_requests(client, super_admin):
    r = client.get("/requests", headers=auth_header(super_admin))
    assert r.status_code == 200


def test_normal_user_cannot_list_all(client, normal_user):
    r = client.get("/requests", headers=auth_header(normal_user))
    assert r.status_code == 403


# --- Assign expert ---

@patch("app.requests.service.send_expert_assigned")
def test_assign_expert(mock_email, client, db, admin_user, normal_user, expert_user, tenant):
    req = req_repo.create_request(db, tenant.id, normal_user.id, "TEST-001", type=RequestType.chc)

    r = client.post(
        f"/requests/{req.id}/assign",
        headers=auth_header(admin_user),
        json={"expert_id": expert_user.id},
    )
    assert r.status_code == 200
    mock_email.assert_called_once()


@patch("app.requests.service.send_expert_assigned")
def test_assign_expert_not_pending(mock_email, client, db, admin_user, normal_user, expert_user, tenant):
    req = req_repo.create_request(db, tenant.id, normal_user.id, "TEST-002", type=RequestType.chc)
    req_repo.update_status(db, req, RequestStatus.cancelled)

    r = client.post(
        f"/requests/{req.id}/assign",
        headers=auth_header(admin_user),
        json={"expert_id": expert_user.id},
    )
    assert r.status_code == 400


# --- Approve request ---

@patch("app.requests.service.send_result_delivered")
def test_approve_request(mock_email, client, db, admin_user, normal_user, tenant):
    req = req_repo.create_request(db, tenant.id, normal_user.id, "TEST-003", type=RequestType.chc)
    req_repo.update_status(db, req, RequestStatus.completed)

    r = client.post(
        f"/requests/{req.id}/approve",
        headers=auth_header(admin_user),
        json={"notes": "Looks good"},
    )
    assert r.status_code == 200


def test_approve_non_completed(client, db, admin_user, normal_user, tenant):
    req = req_repo.create_request(db, tenant.id, normal_user.id, "TEST-004", type=RequestType.chc)

    r = client.post(
        f"/requests/{req.id}/approve",
        headers=auth_header(admin_user),
    )
    assert r.status_code == 400


# --- E-Tariff daily limit ---

@patch("app.requests.service.send_request_confirmation")
@patch("app.core.storage.upload_file", return_value="fake-key")
def test_etariff_daily_limit(mock_s3, mock_confirm, client, db, normal_user, tenant):
    tenant.etariff_daily_limit = 1
    db.flush()

    # First request should succeed
    r1 = client.post(
        "/requests/etariff/manual",
        headers=auth_header(normal_user),
        json={
            "commodity_name": "Item 1",
            "description": "Desc",
            "function": "Fn",
            "material_composition": "Mat",
        },
    )
    assert r1.status_code == 200

    # Second should hit limit
    r2 = client.post(
        "/requests/etariff/manual",
        headers=auth_header(normal_user),
        json={
            "commodity_name": "Item 2",
            "description": "Desc",
            "function": "Fn",
            "material_composition": "Mat",
        },
    )
    assert r2.status_code == 429
