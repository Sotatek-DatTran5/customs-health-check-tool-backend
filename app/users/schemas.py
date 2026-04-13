from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

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
    result_email: str | None = None
    last_login_at: datetime | None = None
    tenant_id: int | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OnboardingRequest(BaseModel):
    """BRD F-U01 — First login onboarding (company profile). All fields required."""
    company_name: str
    tax_code: str
    company_address: str
    contact_person: str
    phone: str
    contact_email: EmailStr
    result_email: EmailStr | None = None  # BRD v8: email nhận kết quả CHC
    industry: str
    company_type: str  # TNHH, Cổ phần, DNTN

    @classmethod
    def validate_tax_code(cls, v: str) -> str:
        """MST: 10 or 13 digits."""
        import re
        cleaned = re.sub(r"[-\s]", "", v)
        if not re.match(r"^\d{10}(\d{3})?$", cleaned):
            raise ValueError("Mã số thuế phải có 10 hoặc 13 chữ số")
        return cleaned

    def model_post_init(self, __context) -> None:
        self.tax_code = self.validate_tax_code(self.tax_code)


class UpdateLocaleRequest(BaseModel):
    locale: str  # vi, en, ko, zh


class AdminCreateRequest(BaseModel):
    """F-A07: Super Admin creates admin for a tenant."""
    email: EmailStr
    full_name: str
    tenant_id: int
