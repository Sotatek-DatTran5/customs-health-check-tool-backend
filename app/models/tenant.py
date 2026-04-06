from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    tenant_code: Mapped[str] = mapped_column(String(50), unique=True)
    subdomain: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Branding (BRD 10.4)
    logo_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # e.g. #1a73e8
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Email domain (BRD 10.4)
    custom_email_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # E-Tariff limit (BRD 10.4)
    etariff_daily_limit: Mapped[int] = mapped_column(Integer, default=10)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    requests: Mapped[list["Request"]] = relationship("Request", back_populates="tenant")
    email_config: Mapped["TenantEmailConfig | None"] = relationship(
        "TenantEmailConfig", back_populates="tenant", uselist=False
    )
