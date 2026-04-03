from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.dashboard import service
from app.dashboard.schemas import DashboardStats, RecentTenant, RecentUser, RecentSubmission, RoleDistribution

router = APIRouter(tags=["dashboard"])

super_admin_only = require_roles(UserRole.super_admin)
allowed_roles = require_roles(UserRole.super_admin, UserRole.tenant_admin, UserRole.expert)


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(allowed_roles)):
    return service.get_stats(db, current_user)


@router.get("/recent-tenants", response_model=list[RecentTenant])
def get_recent_tenants_handler(
    db: Session = Depends(get_db),
    _=Depends(super_admin_only),
    limit: int = Query(default=10, ge=1, le=50),
):
    return service.get_recent_tenants(db, limit)


@router.get("/recent-users", response_model=list[RecentUser])
def get_recent_users_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(allowed_roles),
    limit: int = Query(default=10, ge=1, le=50),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_users(db, tenant_id, limit)


@router.get("/recent-submissions", response_model=list[RecentSubmission])
def get_recent_submissions_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(allowed_roles),
    limit: int = Query(default=10, ge=1, le=50),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_submissions(db, tenant_id, limit)


@router.get("/role-distribution", response_model=RoleDistribution)
def get_role_distribution_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(allowed_roles),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    counts = service.get_role_distribution(db, tenant_id)
    return RoleDistribution(**counts)
