from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_users: int = 0
    total_requests: int = 0

    # Request status breakdown (BRD F-A02)
    requests_pending: int = 0
    requests_processing: int = 0
    requests_completed: int = 0
    requests_delivered: int = 0
    requests_cancelled: int = 0

    # Super admin only
    total_tenants: int | None = None
    active_tenants: int | None = None

    # Period stats
    requests_today: int = 0
    requests_this_week: int = 0
    requests_this_month: int = 0

    class Config:
        from_attributes = True


class RecentTenant(BaseModel):
    id: int
    name: str
    tenant_code: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RecentUser(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecentSubmission(BaseModel):
    id: int
    display_id: str
    type: str
    status: str
    submitted_at: datetime
    uploaded_by: str

    class Config:
        from_attributes = True


class RoleDistribution(BaseModel):
    super_admin: int = 0
    tenant_admin: int = 0
    expert: int = 0
    user: int = 0

    class Config:
        from_attributes = True
