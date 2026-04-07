from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.dashboard import service
from app.dashboard.schemas import DashboardStats, RecentTenant, RecentUser, RecentRequest, RoleDistribution

router = APIRouter()

super_admin_only = require_roles(UserRole.super_admin)
admin_roles = require_roles(UserRole.super_admin, UserRole.tenant_admin)

ADMIN_TAG = "Admin Site — Dashboard"
USER_TAG = "User Site — Dashboard"


@router.get("/stats", response_model=DashboardStats, tags=[USER_TAG, ADMIN_TAG])
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """BRD F-U02/F-A02: Dashboard stats — User (personal), Admin (tenant), Super Admin (cross)."""
    if current_user.role == UserRole.expert:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return service.get_stats(db, current_user)


@router.get("/recent-tenants", response_model=list[RecentTenant], tags=[ADMIN_TAG])
def get_recent_tenants_handler(
    db: Session = Depends(get_db),
    _=Depends(super_admin_only),
    limit: int = Query(default=10, ge=1, le=50),
):
    return service.get_recent_tenants(db, limit)


@router.get("/recent-users", response_model=list[RecentUser], tags=[ADMIN_TAG])
def get_recent_users_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_roles),
    limit: int = Query(default=10, ge=1, le=50),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_users(db, tenant_id, limit)


@router.get("/recent-requests", response_model=list[RecentRequest], tags=[ADMIN_TAG])
def get_recent_requests_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_roles),
    limit: int = Query(default=10, ge=1, le=50),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_requests(db, tenant_id, limit)


@router.get("/role-distribution", response_model=RoleDistribution, tags=[ADMIN_TAG])
def get_role_distribution_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_roles),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    counts = service.get_role_distribution(db, tenant_id)
    return RoleDistribution(**counts)
