import json
from datetime import datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.email_service import send_request_confirmation, send_admin_new_request, send_expert_assigned, send_cancel_notification, send_result_delivered
from app.models.request import Request, RequestFile, RequestStatus, RequestType, CHCModule
from app.models.user import User, UserRole
from app.requests import repository
from app.requests.schemas import CreateManualETariffRequest

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _build_display_id(db: Session, tenant_code: str, tenant_id: int) -> str:
    count = repository.count_by_tenant(db, tenant_id)
    return f"{tenant_code}-{str(count + 1).zfill(3)}"


def _validate_files(files: list[UploadFile]):
    for f in files:
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if f".{ext}" not in ALLOWED_EXTENSIONS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File '{f.filename}' not allowed. Only .xlsx/.xls accepted.")
        # Check file size
        f.file.seek(0, 2)
        size = f.file.tell()
        f.file.seek(0)
        if size > MAX_FILE_SIZE:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File '{f.filename}' exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.")


# ── User actions ──

def create_chc_request(db: Session, files: list[UploadFile], modules: list[str], user: User) -> Request:
    _validate_files(files)
    if not modules:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one CHC module must be selected.")

    display_id = _build_display_id(db, user.tenant.tenant_code, user.tenant_id)
    req = repository.create_request(
        db, user.tenant_id, user.id, display_id,
        type=RequestType.chc,
        chc_modules=modules,
    )

    for up_file in files:
        up_file.file.seek(0, 2)
        file_size = up_file.file.tell()
        up_file.file.seek(0)
        s3_key = f"{user.tenant_id}/requests/{req.id}/{up_file.filename}"
        content = up_file.file.read()
        storage.upload_file(s3_key, content, up_file.content_type or "application/octet-stream")
        repository.create_file(db, req.id, up_file.filename, s3_key, file_size)

    # Emails (BRD AC2, AC3)
    send_request_confirmation(user, req)
    _notify_admins_new_request(db, user.tenant_id, req)

    return req


def create_manual_etariff(db: Session, data: CreateManualETariffRequest, user: User) -> Request:
    # Check daily limit
    _check_etariff_limit(db, user)

    display_id = _build_display_id(db, user.tenant.tenant_code, user.tenant_id)
    input_data = data.model_dump(mode="json")

    req = repository.create_request(
        db, user.tenant_id, user.id, display_id,
        type=RequestType.etariff_manual,
        manual_input_data=json.dumps(input_data, ensure_ascii=False),
    )

    # Store as JSON file in S3
    filename = f"manual_input_{display_id}.json"
    s3_key = f"{user.tenant_id}/requests/{req.id}/{filename}"
    content_bytes = json.dumps(input_data, ensure_ascii=False, indent=2).encode("utf-8")
    storage.upload_file(s3_key, content_bytes, "application/json")
    repository.create_file(db, req.id, filename, s3_key, len(content_bytes))

    send_request_confirmation(user, req)
    return req


def create_batch_etariff(db: Session, files: list[UploadFile], user: User) -> Request:
    _validate_files(files)
    _check_etariff_limit(db, user)

    display_id = _build_display_id(db, user.tenant.tenant_code, user.tenant_id)
    req = repository.create_request(
        db, user.tenant_id, user.id, display_id,
        type=RequestType.etariff_batch,
    )

    for up_file in files:
        up_file.file.seek(0, 2)
        file_size = up_file.file.tell()
        up_file.file.seek(0)
        s3_key = f"{user.tenant_id}/requests/{req.id}/{up_file.filename}"
        content = up_file.file.read()
        storage.upload_file(s3_key, content, up_file.content_type or "application/octet-stream")
        repository.create_file(db, req.id, up_file.filename, s3_key, file_size)

    send_request_confirmation(user, req)
    return req


def cancel_request(db: Session, request_id: int, user: User, reason: str | None = None):
    """BRD F-U04 — User cancels request."""
    req = _get_user_request(db, request_id, user)

    if req.status in (RequestStatus.delivered, RequestStatus.cancelled):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot cancel a delivered or already cancelled request.")

    was_processing = req.status == RequestStatus.processing
    repository.update_status(db, req, RequestStatus.cancelled)
    req.admin_notes = reason
    db.commit()

    send_cancel_notification(db, req, notify_expert=was_processing)
    return req


def get_user_requests(db: Session, user_id: int) -> list[Request]:
    return repository.get_by_user(db, user_id)


def get_user_request_detail(db: Session, request_id: int, user: User) -> Request:
    return _get_user_request(db, request_id, user)


def get_result_download_url(db: Session, request_id: int, file_id: int, user: User) -> dict:
    req = _get_user_request(db, request_id, user)
    if req.status != RequestStatus.delivered:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Results not yet delivered.")
    f = repository.get_file_by_id(db, file_id)
    if not f or f.request_id != req.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    result_key = f.expert_s3_key or f.ai_s3_key
    if not result_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No result available.")
    url = storage.generate_presigned_url(result_key)
    return {"url": url, "filename": f.original_filename}


# ── Admin actions ──

def get_tenant_requests(db: Session, tenant_id: int | None, filters: dict | None = None) -> list[Request]:
    query = db.query(Request)
    if tenant_id:
        query = query.filter(Request.tenant_id == tenant_id)
    if filters:
        if filters.get("status"):
            query = query.filter(Request.status == filters["status"])
        if filters.get("type"):
            query = query.filter(Request.type == filters["type"])
        if filters.get("date_from"):
            query = query.filter(Request.submitted_at >= filters["date_from"])
        if filters.get("date_to"):
            query = query.filter(Request.submitted_at <= filters["date_to"])
        if filters.get("expert_id"):
            query = query.filter(Request.assigned_expert_id == filters["expert_id"])
        if filters.get("search"):
            s = f"%{filters['search']}%"
            query = query.join(User, Request.user_id == User.id).filter(
                or_(Request.display_id.ilike(s), User.full_name.ilike(s), User.email.ilike(s))
            )
    return query.order_by(Request.submitted_at.desc()).all()


def get_request_detail(db: Session, request_id: int, current_user: User) -> Request:
    req = repository.get_by_id(db, request_id)
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found.")
    # Expert can only see assigned requests
    if current_user.role == UserRole.expert and req.assigned_expert_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not assigned to this request.")
    # Admin can only see tenant requests
    if current_user.role == UserRole.tenant_admin and req.tenant_id != current_user.tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request belongs to another tenant.")
    return req


def assign_expert(db: Session, request_id: int, expert_id: int, current_user: User) -> Request:
    """BRD F-A03 — Admin assigns Expert to request. Status → Processing."""
    req = get_request_detail(db, request_id, current_user)
    if req.status != RequestStatus.pending:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only assign expert to pending requests.")

    expert = db.query(User).filter(User.id == expert_id, User.role == UserRole.expert, User.is_active == True).first()
    if not expert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expert not found.")

    repository.assign_expert(db, req, expert_id)
    send_expert_assigned(expert, req)
    return req


def upload_result(db: Session, request_id: int, file_id: int, excel_file: UploadFile | None, pdf_file: UploadFile | None, notes: str | None, current_user: User):
    """BRD F-A03 — Expert uploads result. Status → Completed."""
    req = get_request_detail(db, request_id, current_user)
    if req.status != RequestStatus.processing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Request must be in processing status.")
    if current_user.role == UserRole.expert and req.assigned_expert_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not assigned to this request.")

    f = repository.get_file_by_id(db, file_id)
    if not f or f.request_id != req.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")

    if excel_file:
        s3_key = f"{req.tenant_id}/results/{req.id}/{file_id}/{excel_file.filename}"
        storage.upload_file(s3_key, excel_file.file.read(), excel_file.content_type or "application/octet-stream")
        f.expert_s3_key = s3_key

    if pdf_file:
        s3_key = f"{req.tenant_id}/results/{req.id}/{file_id}/{pdf_file.filename}"
        storage.upload_file(s3_key, pdf_file.file.read(), pdf_file.content_type or "application/pdf")
        f.expert_pdf_s3_key = s3_key

    if notes:
        f.notes = notes
    f.reviewed_by = current_user.id

    # Check if all files have expert results → mark as completed
    all_done = all(rf.expert_s3_key for rf in req.files)
    if all_done:
        repository.update_status(db, req, RequestStatus.completed)

    db.commit()
    return req


def approve_and_deliver(db: Session, request_id: int, notes: str | None, current_user: User) -> Request:
    """BRD F-A03 — Admin approves result. Status → Delivered. Email + link to User."""
    req = get_request_detail(db, request_id, current_user)
    if req.status != RequestStatus.completed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only deliver completed requests.")

    if notes:
        req.admin_notes = notes
    repository.update_status(db, req, RequestStatus.delivered)

    # Send result email to user (BRD AC9, AC10)
    send_result_delivered(db, req)
    return req


def download_file(db: Session, request_id: int, file_id: int, current_user: User):
    req = get_request_detail(db, request_id, current_user)
    f = repository.get_file_by_id(db, file_id)
    if not f or f.request_id != req.id or not f.s3_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    return storage.download_file_stream(f.s3_key)


def get_expert_requests(db: Session, expert_id: int) -> list[Request]:
    return repository.get_by_expert(db, expert_id)


# ── Helpers ──

def _get_user_request(db: Session, request_id: int, user: User) -> Request:
    req = repository.get_by_id(db, request_id)
    if not req or req.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found.")
    return req


def _notify_admins_new_request(db: Session, tenant_id: int, req: Request):
    admins = db.query(User).filter(User.tenant_id == tenant_id, User.role == UserRole.tenant_admin, User.is_active == True).all()
    for admin in admins:
        send_admin_new_request(admin, req)


def _check_etariff_limit(db: Session, user: User):
    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = db.query(Request).filter(
        Request.user_id == user.id,
        Request.type.in_([RequestType.etariff_manual, RequestType.etariff_batch]),
        Request.submitted_at >= today_start,
    ).count()
    limit = user.tenant.etariff_daily_limit if user.tenant else 10
    if today_count >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Daily E-Tariff limit reached ({limit}/day).")
