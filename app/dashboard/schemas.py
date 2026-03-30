from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_tenants: int | None = None
    active_tenants: int | None = None
    total_users: int
    total_records: int
    records_completed: int
    records_processing: int
    records_failed: int
