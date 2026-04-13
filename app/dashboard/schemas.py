from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardStats(BaseModel):
    total_users: int = 0
    total_requests: int = 0

    # Request status breakdown (BRD F-A02)
    requests_pending: int = 0
    requests_ai_processing: int = 0
    requests_pending_assignment: int = 0
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

    model_config = ConfigDict(from_attributes=True)


class ETariffUsageBar(BaseModel):
    period: str  # "2026-04-13" for day, "2026-W15" for week, "2026-04" for month
    row_count: int
    request_count: int


class SatisfactionScore(BaseModel):
    average_rating: float | None = None
    total_rated: int = 0
    rating_breakdown: dict[str, int] = {}  # {"1": 0, "2": 1, ...}


class SLAOverdue(BaseModel):
    warning_count: int = 0  # processing > 48h
    breach_count: int = 0   # processing > 72h


class RecentTenant(BaseModel):
    id: int
    name: str
    tenant_code: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecentUser(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecentRequest(BaseModel):
    id: int
    display_id: str
    type: str
    status: str
    submitted_at: datetime
    uploaded_by: str

    model_config = ConfigDict(from_attributes=True)


class RoleDistribution(BaseModel):
    super_admin: int = 0
    tenant_admin: int = 0
    expert: int = 0
    user: int = 0

    model_config = ConfigDict(from_attributes=True)
