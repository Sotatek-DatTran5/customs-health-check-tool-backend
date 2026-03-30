from datetime import datetime

from pydantic import BaseModel

from app.models.submission import AIStatus, DeliveryStatus


class SubmissionFileResponse(BaseModel):
    id: int
    original_filename: str
    ai_status: AIStatus
    delivery_status: DeliveryStatus
    published_at: datetime | None

    class Config:
        from_attributes = True


class SubmissionResponse(BaseModel):
    id: int
    display_id: str
    submitted_at: datetime
    files: list[SubmissionFileResponse] = []

    class Config:
        from_attributes = True


class UpdateResultRequest(BaseModel):
    notes: str | None = None
