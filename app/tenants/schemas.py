from datetime import datetime

from pydantic import BaseModel, EmailStr


class TenantAdminInfo(BaseModel):
    email: EmailStr
    full_name: str


class TenantCreate(BaseModel):
    name: str
    tenant_code: str
    description: str | None = None
    is_active: bool = True
    admin_email: EmailStr
    admin_full_name: str


class TenantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    admin_email: EmailStr | None = None
    admin_full_name: str | None = None


class TenantResponse(BaseModel):
    id: int
    name: str
    tenant_code: str
    subdomain: str
    description: str | None
    is_active: bool
    created_at: datetime
    admin: TenantAdminInfo | None = None

    class Config:
        from_attributes = True
