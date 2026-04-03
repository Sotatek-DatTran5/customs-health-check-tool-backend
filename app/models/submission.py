import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIStatus(str, enum.Enum):
    not_started = "not_started"
    running = "running"
    completed = "completed"
    failed = "failed"


class DeliveryStatus(str, enum.Enum):
    not_sent = "not_sent"
    sent = "sent"
    failed = "failed"


class SubmissionType(str, enum.Enum):
    file_upload = "file_upload"
    batch_dataset = "batch_dataset"
    manual_input = "manual_input"


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    display_id: Mapped[str] = mapped_column(String(50), unique=True)  # e.g. ACME-001
    type: Mapped[SubmissionType] = mapped_column(Enum(SubmissionType), default=SubmissionType.file_upload)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="submissions")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    files: Mapped[list["SubmissionFile"]] = relationship("SubmissionFile", back_populates="submission")


class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    s3_key: Mapped[str] = mapped_column(String(500))
    ai_status: Mapped[AIStatus] = mapped_column(Enum(AIStatus), default=AIStatus.not_started)
    ai_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expert_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus), default=DeliveryStatus.not_sent)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    submission: Mapped["Submission"] = relationship("Submission", back_populates="files")
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewed_by])
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship("AnalysisJob", back_populates="submission_file")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_file_id: Mapped[int] = mapped_column(ForeignKey("submission_files.id"))
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    submission_file: Mapped["SubmissionFile"] = relationship("SubmissionFile", back_populates="analysis_jobs")
