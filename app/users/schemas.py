from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    tenant_id: int | None

    class Config:
        from_attributes = True
