from datetime import datetime

from pydantic import BaseModel

from app.models.submission import AIStatus, DeliveryStatus


class SubmissionFileResponse(BaseModel):
    id: int
    submission_id: int
    original_filename: str
    ai_status: AIStatus
    delivery_status: DeliveryStatus
    published_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class SubmissionResponse(BaseModel):
    id: int
    display_id: str
    type: str
    submitted_at: datetime
    files: list[SubmissionFileResponse] = []

    class Config:
        from_attributes = True


class ManualInputRequest(BaseModel):
    commodity_name: str
    description: str
    function: str
    structure_components: str
    material_composition: str
    technical_specification: str
    additional_notes: str | None = None


class UpdateResultRequest(BaseModel):
    notes: str | None = None
