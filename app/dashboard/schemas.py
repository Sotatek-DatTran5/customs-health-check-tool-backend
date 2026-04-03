from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_tenants: int | None = None
    active_tenants: int | None = None
    total_users: int
    total_records: int
    records_completed: int
    records_processing: int
    records_failed: int

    class Config:
        from_attributes = True


class RecentTenant(BaseModel):
    id: int
    name: str
    tenant_code: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecentUser(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    created_at: datetime

    # NOTE: role returned as str (role.value) for simplicity in serialization
    # Compare with UserResponse in app/users/schemas.py which uses UserRole enum directly

    class Config:
        from_attributes = True


class RecentSubmission(BaseModel):
    id: int
    display_id: str
    type: str
    submitted_at: datetime
    uploaded_by: str  # full_name of user

    class Config:
        from_attributes = True


class RoleDistribution(BaseModel):
    super_admin: int
    tenant_admin: int
    expert: int
    user: int

    class Config:
        from_attributes = True
