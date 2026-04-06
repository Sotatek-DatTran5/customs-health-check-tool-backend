from datetime import datetime

from pydantic import BaseModel, EmailStr


class TenantCreate(BaseModel):
    name: str
    tenant_code: str
    description: str | None = None
    is_active: bool = True
    admin_email: EmailStr
    admin_full_name: str
    # Branding (BRD 10.4)
    primary_color: str | None = None
    display_name: str | None = None
    # E-Tariff limit
    etariff_daily_limit: int = 10


class TenantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    # Branding
    primary_color: str | None = None
    display_name: str | None = None
    custom_email_domain: str | None = None
    etariff_daily_limit: int | None = None


class TenantResponse(BaseModel):
    id: int
    name: str
    tenant_code: str
    subdomain: str
    description: str | None = None
    is_active: bool
    logo_s3_key: str | None = None
    primary_color: str | None = None
    display_name: str | None = None
    custom_email_domain: str | None = None
    etariff_daily_limit: int = 10
    created_at: datetime

    class Config:
        from_attributes = True


class ExpertCreate(BaseModel):
    """F-A05: Admin creates cross-tenant expert."""
    email: EmailStr
    full_name: str


class ExpertResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True
