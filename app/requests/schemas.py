import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.request import CHCModule, RequestStatus, RequestType, USER_FACING_STATUS_MAP


# ── Response schemas ──

class RequestFileResponse(BaseModel):
    id: int
    request_id: int
    original_filename: str
    file_size: int | None = None
    ai_status: str
    ai_task_id: str | None = None
    ai_result_data: dict | None = None
    expert_s3_key: str | None = None
    expert_pdf_s3_key: str | None = None
    notes: str | None = None
    created_at: datetime

    @field_validator("ai_result_data", mode="before")
    @classmethod
    def parse_ai_result_data(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class RequestResponse(BaseModel):
    id: int
    display_id: str
    type: str
    status: str
    user_facing_status: str | None = None
    chc_modules: list[str] | None = None
    assigned_expert_id: int | None = None
    assigned_expert_name: str | None = None
    submitted_at: datetime
    completed_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    admin_notes: str | None = None
    has_downloaded: bool = False
    has_rated: bool = False
    rating: int | None = None
    pricing_tier: str | None = None
    files: list[RequestFileResponse] = []
    user_name: str | None = None
    user_email: str | None = None

    @model_validator(mode="after")
    def compute_derived_fields(self):
        # User-facing status mapping
        if self.user_facing_status is None and self.status:
            try:
                self.user_facing_status = USER_FACING_STATUS_MAP[RequestStatus(self.status)]
            except (ValueError, KeyError):
                self.user_facing_status = self.status
        # Pricing tier for CHC requests (BRD v8)
        if self.pricing_tier is None and self.type == "chc" and self.chc_modules:
            n = len(self.chc_modules)
            self.pricing_tier = "Gói Toàn diện" if n >= 3 else "Gói Cơ bản"
        return self

    model_config = ConfigDict(from_attributes=True)


# ── Presigned URL upload schemas (BRD v8) ──

class PresignedURLRequest(BaseModel):
    """Step 1: Request presigned upload URL."""
    filename: str
    file_size: int
    request_type: RequestType
    chc_modules: list[CHCModule] | None = None


class PresignedURLResponse(BaseModel):
    request_id: int
    file_id: int
    display_id: str
    upload_url: str
    s3_key: str
    expires_in: int = 900


class ConfirmUploadResponse(BaseModel):
    request_id: int
    display_id: str
    status: str
    row_count: int | None = None
    quota_remaining: int | None = None
    warning: str | None = None


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


class RateRequest(BaseModel):
    """User rates a delivered request (1-5 stars)."""
    rating: int
    comment: str | None = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5.")
        return v


class ReassignExpertRequest(BaseModel):
    expert_id: int
    reason: str | None = None


# ── Filter schema ──

class RequestFilterParams(BaseModel):
    status: RequestStatus | None = None
    type: RequestType | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None
    expert_id: int | None = None
