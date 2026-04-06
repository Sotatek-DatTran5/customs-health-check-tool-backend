from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.models.request import Request, RequestStatus


def get_stats(db: Session, current_user: User) -> dict:
    stats = {}
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    if current_user.role == UserRole.super_admin:
        stats["total_tenants"] = db.query(Tenant).count()
        stats["active_tenants"] = db.query(Tenant).filter(Tenant.is_active == True).count()
        stats["total_users"] = db.query(User).filter(User.role != UserRole.super_admin).count()
        base = db.query(Request)
    else:
        tenant_id = current_user.tenant_id
        stats["total_users"] = db.query(User).filter(User.tenant_id == tenant_id).count()
        base = db.query(Request).filter(Request.tenant_id == tenant_id)

    stats["total_requests"] = base.count()
    stats["requests_pending"] = base.filter(Request.status == RequestStatus.pending).count()
    stats["requests_processing"] = base.filter(Request.status == RequestStatus.processing).count()
    stats["requests_completed"] = base.filter(Request.status == RequestStatus.completed).count()
    stats["requests_delivered"] = base.filter(Request.status == RequestStatus.delivered).count()
    stats["requests_cancelled"] = base.filter(Request.status == RequestStatus.cancelled).count()

    stats["requests_today"] = base.filter(Request.submitted_at >= today_start).count()
    stats["requests_this_week"] = base.filter(Request.submitted_at >= week_start).count()
    stats["requests_this_month"] = base.filter(Request.submitted_at >= month_start).count()

    return stats


def get_recent_tenants(db: Session, limit: int = 10) -> list[Tenant]:
    return db.query(Tenant).order_by(Tenant.created_at.desc()).limit(limit).all()


def get_recent_users(db: Session, tenant_id: int | None, limit: int = 10) -> list[User]:
    query = db.query(User)
    if tenant_id:
        query = query.filter(User.tenant_id == tenant_id)
    return query.order_by(User.created_at.desc()).limit(limit).all()


def get_recent_requests(db: Session, tenant_id: int | None, limit: int = 10) -> list[dict]:
    query = db.query(Request).join(User, Request.user_id == User.id)
    if tenant_id:
        query = query.filter(Request.tenant_id == tenant_id)
    results = query.order_by(Request.submitted_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "display_id": r.display_id,
            "type": r.type.value,
            "status": r.status.value,
            "submitted_at": r.submitted_at,
            "uploaded_by": r.user.full_name,
        }
        for r in results
    ]


def get_role_distribution(db: Session, tenant_id: int | None = None) -> dict:
    query = db.query(User.role, func.count(User.id)).group_by(User.role)
    if tenant_id:
        query = query.filter(User.tenant_id == tenant_id)
    counts = {role.value: 0 for role in UserRole}
    for role, count in query.all():
        counts[role.value] = count
    return counts
