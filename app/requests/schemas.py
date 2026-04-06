from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.request import CHCModule, RequestStatus, RequestType


# ── Response schemas ──

class RequestFileResponse(BaseModel):
    id: int
    request_id: int
    original_filename: str
    file_size: int | None = None
    ai_status: str
    expert_s3_key: str | None = None
    expert_pdf_s3_key: str | None = None
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequestResponse(BaseModel):
    id: int
    display_id: str
    type: str
    status: str
    chc_modules: list[str] | None = None
    assigned_expert_id: int | None = None
    assigned_expert_name: str | None = None
    submitted_at: datetime
    completed_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    admin_notes: str | None = None
    files: list[RequestFileResponse] = []
    user_name: str | None = None
    user_email: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ── Create schemas ──

class CreateCHCRequest(BaseModel):
    """User creates a CHC order — uploads ECUS file + picks modules."""
    chc_modules: list[CHCModule]


class CreateManualETariffRequest(BaseModel):
    """User creates an E-Tariff manual classification request."""
    commodity_name: str
    scientific_name: str | None = None
    description: str
    function: str
    material_composition: str
    structure_components: str | None = None
    technical_specification: str | None = None
    additional_info: list[dict] | None = None  # [{label, value}]


# ── Admin action schemas ──

class AssignExpertRequest(BaseModel):
    expert_id: int


class ApproveRequest(BaseModel):
    notes: str | None = None


class CancelRequest(BaseModel):
    reason: str | None = None


# ── Filter schema ──

class RequestFilterParams(BaseModel):
    status: RequestStatus | None = None
    type: RequestType | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None
    expert_id: int | None = None
