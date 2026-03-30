from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.models.submission import Submission, SubmissionFile, AIStatus


def get_stats(db: Session, current_user: User) -> dict:
    stats = {}

    if current_user.role == UserRole.super_admin:
        stats["total_tenants"] = db.query(Tenant).count()
        stats["active_tenants"] = db.query(Tenant).filter(Tenant.is_active == True).count()
        stats["total_users"] = db.query(User).filter(User.role.in_([UserRole.user, UserRole.expert, UserRole.tenant_admin])).count()
        stats["total_records"] = db.query(SubmissionFile).count()
    else:
        # tenant_admin và expert chỉ thấy trong tenant
        tenant_id = current_user.tenant_id
        stats["total_users"] = db.query(User).filter(User.tenant_id == tenant_id).count()
        stats["total_records"] = db.query(SubmissionFile).join(Submission).filter(Submission.tenant_id == tenant_id).count()

    # Breakdown theo AI status (cho tenant_admin và expert)
    if current_user.role != UserRole.super_admin:
        tenant_id = current_user.tenant_id
        base = db.query(SubmissionFile).join(Submission).filter(Submission.tenant_id == tenant_id)
        stats["records_completed"] = base.filter(SubmissionFile.ai_status == AIStatus.completed).count()
        stats["records_processing"] = base.filter(SubmissionFile.ai_status == AIStatus.running).count()
        stats["records_failed"] = base.filter(SubmissionFile.ai_status == AIStatus.failed).count()
    else:
        stats["records_completed"] = db.query(SubmissionFile).filter(SubmissionFile.ai_status == AIStatus.completed).count()
        stats["records_processing"] = db.query(SubmissionFile).filter(SubmissionFile.ai_status == AIStatus.running).count()
        stats["records_failed"] = db.query(SubmissionFile).filter(SubmissionFile.ai_status == AIStatus.failed).count()

    return stats
