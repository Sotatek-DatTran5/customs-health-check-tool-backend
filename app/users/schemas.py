from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str | None = None  # auto-gen if not provided
    role: UserRole = UserRole.user


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    phone: str | None = None
    contact_email: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_first_login: bool
    locale: str
    company_name: str | None = None
    tax_code: str | None = None
    phone: str | None = None
    last_login_at: datetime | None = None
    tenant_id: int | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class OnboardingRequest(BaseModel):
    """BRD F-U01 — First login onboarding (company profile)."""
    company_name: str
    tax_code: str
    company_address: str
    contact_person: str
    phone: str
    contact_email: EmailStr | None = None
    industry: str | None = None
    company_type: str | None = None  # TNHH, Cổ phần, DNTN


class UpdateLocaleRequest(BaseModel):
    locale: str  # vi, en, ko, zh
