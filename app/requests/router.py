from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_onboarding_complete, require_roles
from app.models.request import RequestStatus, RequestType
from app.models.user import User, UserRole
from app.requests import service, presigned_service
from app.requests.schemas import (
    ApproveRequest,
    AssignExpertRequest,
    CancelRequest,
    ConfirmUploadResponse,
    CreateManualETariffRequest,
    PresignedURLRequest,
    PresignedURLResponse,
    RateRequest,
    ReassignExpertRequest,
    RequestResponse,
)

router = APIRouter()

admin_or_expert = require_roles(UserRole.tenant_admin, UserRole.expert, UserRole.super_admin)
admin_only = require_roles(UserRole.tenant_admin, UserRole.super_admin)
expert_only = require_roles(UserRole.expert)
user_only = require_roles(UserRole.user)

USER_TAG = "User Site — Requests"
ADMIN_TAG = "Admin Site — Requests"


# ════════════════════════════════════════════════════
#  USER PORTAL endpoints
# ════════════════════════════════════════════════════

@router.post("/presigned-url", response_model=PresignedURLResponse, tags=[USER_TAG])
def request_presigned_url(
    payload: PresignedURLRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_onboarding_complete),
):
    """BRD v8 Step 1: Create request + return presigned S3 upload URL."""
    return presigned_service.request_presigned_url(
        db, payload.filename, payload.file_size, payload.request_type.value,
        [m.value for m in payload.chc_modules] if payload.chc_modules else None,
        current_user,
    )


@router.post("/{request_id}/confirm-upload", response_model=ConfirmUploadResponse, tags=[USER_TAG])
def confirm_upload(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_onboarding_complete),
):
    """BRD v8 Step 3: Confirm S3 upload → validate file, start AI processing."""
    return presigned_service.confirm_upload(db, request_id, current_user)


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


@router.post("/my/{request_id}/retry", response_model=RequestResponse, tags=[USER_TAG])
def retry_etariff(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AC6: Retry E-Tariff when AI failed."""
    return service.retry_etariff(db, request_id, current_user)


@router.post("/my/{request_id}/rate", response_model=RequestResponse, tags=[USER_TAG])
def rate_request(
    request_id: int,
    payload: RateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """BRD v8 — User rates a delivered request (1-5 stars)."""
    return service.rate_request(db, request_id, payload.rating, payload.comment, current_user)


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


@router.post("/{request_id}/reassign", tags=[ADMIN_TAG])
def reassign_expert(
    request_id: int,
    payload: ReassignExpertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    """BRD v8 — Admin reassigns Expert (while processing). Notify both."""
    return service.reassign_expert(db, request_id, payload.expert_id, payload.reason, current_user)


@router.post("/{request_id}/files/{file_id}/upload-result", tags=[ADMIN_TAG])
def upload_result(
    request_id: int,
    file_id: int,
    excel_file: UploadFile | None = File(None),
    pdf_file: UploadFile | None = File(None),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_only),
):
    """F-A03: Expert uploads result (Excel + PDF) → status=Completed."""
    return service.upload_result(db, request_id, file_id, excel_file, pdf_file, notes, current_user)


# ════════════════════════════════════════════════════
#  INTERNAL WEBHOOK (server-to-server, no user auth)
# ════════════════════════════════════════════════════


class AICallbackPayload(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


@router.post("/webhook/ai-result", tags=["Internal"])
def ai_result_callback(
    payload: AICallbackPayload,
    db: Session = Depends(get_db),
    x_webhook_secret: Optional[str] = Header(None),
):
    """Webhook called by Report Service when AI task completes."""
    if settings.WEBHOOK_SECRET and x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    return service.handle_ai_callback(
        db, payload.task_id, payload.status, payload.result, payload.error,
    )


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
