from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ETariffUsageLog(Base):
    """BRD v3/v5 — Log every E-Tariff lookup for analytics and pricing strategy."""
    __tablename__ = "etariff_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"))
    mode: Mapped[str] = mapped_column(String(20))  # "manual" | "batch"
    row_count: Mapped[int] = mapped_column(Integer, default=1)  # 1 for manual, N for batch
    query_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship("User")
    tenant: Mapped["Tenant"] = relationship("Tenant")
    request: Mapped["Request"] = relationship("Request")
