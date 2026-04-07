from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_onboarding_complete, require_roles
from app.models.request import RequestStatus, RequestType
from app.models.user import User, UserRole
from app.requests import service
from app.requests.schemas import (
    ApproveRequest,
    AssignExpertRequest,
    CancelRequest,
    CreateManualETariffRequest,
    RequestResponse,
)

router = APIRouter()

admin_or_expert = require_roles(UserRole.tenant_admin, UserRole.expert, UserRole.super_admin)
admin_only = require_roles(UserRole.tenant_admin, UserRole.super_admin)

USER_TAG = "User Site — Requests"
ADMIN_TAG = "Admin Site — Requests"


# ════════════════════════════════════════════════════
#  USER PORTAL endpoints
# ════════════════════════════════════════════════════

@router.post("/chc", response_model=RequestResponse, tags=[USER_TAG])
def create_chc_request(
    files: list[UploadFile] = File(...),
    chc_modules: list[str] = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_onboarding_complete),
):
    """F-U03: User creates CHC order (upload ECUS + pick modules)."""
    return service.create_chc_request(db, files, chc_modules, current_user)


@router.post("/etariff/manual", response_model=RequestResponse, tags=[USER_TAG])
def create_manual_etariff(
    payload: CreateManualETariffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_onboarding_complete),
):
    """F-U05: E-Tariff Manual Mode."""
    return service.create_manual_etariff(db, payload, current_user)


@router.post("/etariff/batch", response_model=RequestResponse, tags=[USER_TAG])
def create_batch_etariff(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_onboarding_complete),
):
    """F-U06: E-Tariff Batch Mode."""
    return service.create_batch_etariff(db, files, current_user)


@router.get("/my", response_model=list[RequestResponse], tags=[USER_TAG])
def get_my_requests(
    status: RequestStatus | None = None,
    type: RequestType | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """F-U02: User views their requests (with optional filters)."""
    filters = {"status": status, "type": type}
    return service.get_user_requests(db, current_user.id, filters)


@router.get("/my/{request_id}", response_model=RequestResponse, tags=[USER_TAG])
def get_my_request_detail(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_user_request_detail(db, request_id, current_user)


@router.post("/my/{request_id}/cancel", response_model=RequestResponse, tags=[USER_TAG])
def cancel_request(
    request_id: int,
    payload: CancelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """F-U04: User cancels request."""
    reason = payload.reason if payload else None
    return service.cancel_request(db, request_id, current_user, reason)


@router.get("/my/{request_id}/files/{file_id}/result", tags=[USER_TAG])
def get_result_url(
    request_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """F-U02: User downloads result (Excel/PDF)."""
    return service.get_result_download_url(db, request_id, file_id, current_user)


# ════════════════════════════════════════════════════
#  ADMIN PORTAL endpoints
# ════════════════════════════════════════════════════

@router.get("", response_model=list[RequestResponse], tags=[ADMIN_TAG])
def list_requests(
    status: RequestStatus | None = None,
    type: RequestType | None = None,
    search: str | None = None,
    expert_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_expert),
):
    """F-A03: Admin/Expert views request list."""
    if current_user.role == UserRole.expert:
        return service.get_expert_requests(db, current_user.id)
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    filters = {"status": status, "type": type, "search": search, "expert_id": expert_id}
    return service.get_tenant_requests(db, tenant_id, filters)


@router.get("/{request_id}", response_model=RequestResponse, tags=[ADMIN_TAG])
def get_request_detail(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_expert),
):
    return service.get_request_detail(db, request_id, current_user)


@router.get("/{request_id}/files/{file_id}/download", tags=[ADMIN_TAG])
def download_file(
    request_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_expert),
):
    return service.download_file(db, request_id, file_id, current_user)


@router.post("/{request_id}/assign", tags=[ADMIN_TAG])
def assign_expert(
    request_id: int,
    payload: AssignExpertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    """F-A03: Admin assigns Expert → status=Processing."""
    return service.assign_expert(db, request_id, payload.expert_id, current_user)


@router.post("/{request_id}/files/{file_id}/upload-result", tags=[ADMIN_TAG])
def upload_result(
    request_id: int,
    file_id: int,
    excel_file: UploadFile | None = File(None),
    pdf_file: UploadFile | None = File(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_expert),
):
    """F-A03: Expert uploads result (Excel + PDF) → status=Completed."""
    return service.upload_result(db, request_id, file_id, excel_file, pdf_file, notes, current_user)


@router.post("/{request_id}/approve", tags=[ADMIN_TAG])
def approve_request(
    request_id: int,
    payload: ApproveRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    """F-A03: Admin approves → status=Delivered, email User."""
    notes = payload.notes if payload else None
    return service.approve_and_deliver(db, request_id, notes, current_user)
