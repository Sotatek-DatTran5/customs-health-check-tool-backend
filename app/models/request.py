import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RequestStatus(str, enum.Enum):
    """BRD 6.2 — Request Status Flow"""
    pending = "pending"          # User vừa tạo, chờ Admin xử lý
    processing = "processing"    # Admin đã assign Expert, đang xử lý
    completed = "completed"      # Expert đã upload kết quả, chờ Admin duyệt
    delivered = "delivered"      # Admin đã duyệt, kết quả đã gửi User
    cancelled = "cancelled"      # User hủy đơn


class RequestType(str, enum.Enum):
    chc = "chc"                  # Custom Health Check (file upload + modules)
    etariff_manual = "etariff_manual"   # E-Tariff Manual Mode
    etariff_batch = "etariff_batch"     # E-Tariff Batch Mode


class CHCModule(str, enum.Enum):
    """BRD 5.2.1 — CHC Modules"""
    item_code_generator = "item_code_generator"
    tariff_classification = "tariff_classification"
    customs_valuation = "customs_valuation"
    non_tariff_measures = "non_tariff_measures"
    exim_statistics = "exim_statistics"


class Request(Base):
    """
    Central model for all user requests (CHC orders + E-Tariff).
    Maps to BRD section 6 Business Flow.
    """
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    display_id: Mapped[str] = mapped_column(String(50), unique=True)  # e.g. ACME-001

    type: Mapped[RequestType] = mapped_column(Enum(RequestType), default=RequestType.chc)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.pending)

    # CHC modules selected (BRD 5.2.1) — stored as array of enum values
    chc_modules: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)

    # Expert assignment (BRD 6.1)
    assigned_expert_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # E-Tariff manual input data (JSON stored as text)
    manual_input_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Admin notes
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="requests")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    assigned_expert: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_expert_id])
    files: Mapped[list["RequestFile"]] = relationship("RequestFile", back_populates="request", cascade="all, delete-orphan")


class RequestFile(Base):
    """Files attached to a request (ECUS upload, AI result, expert result)."""
    __tablename__ = "request_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"))

    # Upload info
    original_filename: Mapped[str] = mapped_column(String(255))
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes

    # AI processing
    ai_status: Mapped[str] = mapped_column(String(20), default="not_started")  # not_started, running, completed, failed
    ai_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # Report Service task_id for callback/polling
    ai_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_result_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # Structured JSON from Report Service

    # Expert result
    expert_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Excel
    expert_pdf_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)  # PDF report
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    request: Mapped["Request"] = relationship("Request", back_populates="files")
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by])
