from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.models.request import Request, RequestStatus
from app.models.etariff_usage_log import ETariffUsageLog


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
    elif current_user.role == UserRole.user:
        # BRD F-U02: User sees personal stats only
        base = db.query(Request).filter(Request.user_id == current_user.id)
    else:
        tenant_id = current_user.tenant_id
        stats["total_users"] = db.query(User).filter(User.tenant_id == tenant_id).count()
        base = db.query(Request).filter(Request.tenant_id == tenant_id)

    stats["total_requests"] = base.count()
    stats["requests_pending"] = base.filter(Request.status == RequestStatus.pending).count()
    stats["requests_ai_processing"] = base.filter(Request.status == RequestStatus.ai_processing).count()
    stats["requests_pending_assignment"] = base.filter(Request.status == RequestStatus.pending_assignment).count()
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


def get_etariff_usage(db: Session, tenant_id: int | None, period: str = "day") -> list[dict]:
    """BRD v8 — E-Tariff usage bar chart (daily/weekly/monthly)."""
    now = datetime.now(timezone.utc)
    if period == "day":
        start = now - timedelta(days=30)
        fmt = func.to_char(ETariffUsageLog.created_at, "YYYY-MM-DD")
    elif period == "week":
        start = now - timedelta(weeks=12)
        fmt = func.to_char(ETariffUsageLog.created_at, "IYYY-\"W\"IW")
    else:  # month
        start = now - timedelta(days=365)
        fmt = func.to_char(ETariffUsageLog.created_at, "YYYY-MM")

    query = db.query(
        fmt.label("period"),
        func.coalesce(func.sum(ETariffUsageLog.row_count), 0).label("row_count"),
        func.count(ETariffUsageLog.id).label("request_count"),
    ).filter(ETariffUsageLog.created_at >= start)
    if tenant_id:
        query = query.filter(ETariffUsageLog.tenant_id == tenant_id)

    rows = query.group_by("period").order_by("period").all()
    return [{"period": r.period, "row_count": int(r.row_count), "request_count": r.request_count} for r in rows]


def get_satisfaction_score(db: Session, tenant_id: int | None) -> dict:
    """BRD v8 — Average rating + breakdown."""
    base = db.query(Request).filter(Request.has_rated == True, Request.rating.isnot(None))
    if tenant_id:
        base = base.filter(Request.tenant_id == tenant_id)

    avg_result = base.with_entities(func.avg(Request.rating), func.count(Request.id)).first()
    avg_rating = float(avg_result[0]) if avg_result and avg_result[0] is not None else None
    total_rated = avg_result[1] if avg_result else 0

    breakdown = {str(i): 0 for i in range(1, 6)}
    for rating, count in base.with_entities(Request.rating, func.count(Request.id)).group_by(Request.rating).all():
        breakdown[str(rating)] = count

    return {
        "average_rating": round(avg_rating, 2) if avg_rating is not None else None,
        "total_rated": total_rated,
        "rating_breakdown": breakdown,
    }


def get_sla_overdue(db: Session, tenant_id: int | None) -> dict:
    """BRD v8 — Count requests in processing >48h (warning) and >72h (breach)."""
    now = datetime.now(timezone.utc)
    warning_threshold = now - timedelta(hours=48)
    breach_threshold = now - timedelta(hours=72)

    base = db.query(Request).filter(
        Request.status == RequestStatus.processing,
        Request.assigned_at.isnot(None),
    )
    if tenant_id:
        base = base.filter(Request.tenant_id == tenant_id)

    warning_count = base.filter(
        Request.assigned_at < warning_threshold,
        Request.assigned_at >= breach_threshold,
    ).count()
    breach_count = base.filter(Request.assigned_at < breach_threshold).count()

    return {"warning_count": warning_count, "breach_count": breach_count}
