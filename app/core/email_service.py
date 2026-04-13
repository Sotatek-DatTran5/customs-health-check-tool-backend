"""
Email service with template support for all 7 BRD email types.
Uses SMTP (MailHog in dev) with plain text + optional HTML.
"""
import logging

from sqlalchemy.orm import Session

from app.core.email import send_email
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── i18n email subjects ──
SUBJECTS = {
    "vi": {
        "welcome": "CHC — Chào mừng bạn đến với {tenant_name}",
        "request_confirmation": "CHC — Đơn {display_id} đã được tiếp nhận",
        "admin_new_request": "CHC — Đơn mới {display_id} cần xử lý",
        "expert_assigned": "CHC — Bạn được giao xử lý đơn {display_id}",
        "cancel_notification": "CHC — Đơn {display_id} đã bị hủy",
        "result_uploaded": "CHC — Kết quả đơn {display_id} đã sẵn sàng để duyệt",
        "result_delivered": "CHC — Kết quả đơn {display_id} đã hoàn thành",
        "password_reset": "CHC — Đặt lại mật khẩu",
        "expert_reassigned_removed": "CHC — Bạn đã được gỡ khỏi đơn {display_id}",
        "expert_reassigned_new": "CHC — Bạn được chuyển giao đơn {display_id}",
        "wp_draft_ready": "CHC — WP Draft của đơn {display_id} đã sẵn sàng",
        "sla_warning": "CHC — Cảnh báo SLA: đơn {display_id} quá 48h",
        "sla_breach": "CHC — Vi phạm SLA: đơn {display_id} quá 72h",
    },
    "en": {
        "welcome": "CHC — Welcome to {tenant_name}",
        "request_confirmation": "CHC — Request {display_id} received",
        "admin_new_request": "CHC — New request {display_id} needs attention",
        "expert_assigned": "CHC — You have been assigned request {display_id}",
        "cancel_notification": "CHC — Request {display_id} has been cancelled",
        "result_uploaded": "CHC — Results for {display_id} ready for review",
        "result_delivered": "CHC — Results for {display_id} delivered",
        "password_reset": "CHC — Password Reset",
        "expert_reassigned_removed": "CHC — Removed from request {display_id}",
        "expert_reassigned_new": "CHC — You have been reassigned request {display_id}",
        "wp_draft_ready": "CHC — WP Draft ready for request {display_id}",
        "sla_warning": "CHC — SLA Warning: request {display_id} overdue 48h",
        "sla_breach": "CHC — SLA Breach: request {display_id} overdue 72h",
    },
    "ko": {
        "welcome": "CHC — {tenant_name}에 오신 것을 환영합니다",
        "request_confirmation": "CHC — 요청 {display_id}이(가) 접수되었습니다",
        "admin_new_request": "CHC — 새로운 요청 {display_id}",
        "expert_assigned": "CHC — 요청 {display_id}이(가) 배정되었습니다",
        "cancel_notification": "CHC — 요청 {display_id}이(가) 취소되었습니다",
        "result_uploaded": "CHC — {display_id} 결과 검토 준비 완료",
        "result_delivered": "CHC — {display_id} 결과 전달 완료",
        "password_reset": "CHC — 비밀번호 재설정",
        "expert_reassigned_removed": "CHC — 요청 {display_id}에서 제외되었습니다",
        "expert_reassigned_new": "CHC — 요청 {display_id}이(가) 재배정되었습니다",
        "wp_draft_ready": "CHC — 요청 {display_id} WP 초안 준비 완료",
        "sla_warning": "CHC — SLA 경고: 요청 {display_id} 48시간 초과",
        "sla_breach": "CHC — SLA 위반: 요청 {display_id} 72시간 초과",
    },
    "zh": {
        "welcome": "CHC — 欢迎加入 {tenant_name}",
        "request_confirmation": "CHC — 请求 {display_id} 已收到",
        "admin_new_request": "CHC — 新请求 {display_id} 需要处理",
        "expert_assigned": "CHC — 您已被分配请求 {display_id}",
        "cancel_notification": "CHC — 请求 {display_id} 已取消",
        "result_uploaded": "CHC — {display_id} 结果已准备好审核",
        "result_delivered": "CHC — {display_id} 结果已交付",
        "password_reset": "CHC — 重置密码",
        "expert_reassigned_removed": "CHC — 已从请求 {display_id} 中移除",
        "expert_reassigned_new": "CHC — 您已被重新分配请求 {display_id}",
        "wp_draft_ready": "CHC — 请求 {display_id} WP草稿已就绪",
        "sla_warning": "CHC — SLA警告: 请求 {display_id} 超过48小时",
        "sla_breach": "CHC — SLA违规: 请求 {display_id} 超过72小时",
    },
}


def _get_subject(locale: str, template_key: str, **kwargs) -> str:
    templates = SUBJECTS.get(locale, SUBJECTS["vi"])
    return templates.get(template_key, template_key).format(**kwargs)


# ── 1. Welcome email (BRD #1 — account creation) ──

def send_welcome_email(user, tenant_name: str, password: str):
    locale = getattr(user, "locale", "vi")
    subject = _get_subject(locale, "welcome", tenant_name=tenant_name)

    # BRD Email #1: Link to tenant subdomain for users, admin portal for admin/expert
    from app.models.user import UserRole
    if getattr(user, "role", None) == UserRole.user and getattr(user, "tenant", None):
        login_url = f"http://{user.tenant.subdomain}.{settings.BASE_DOMAIN}/auth/login"
    else:
        login_url = f"http://{settings.ADMIN_DOMAIN}/auth/login"

    body = (
        f"Email: {user.email}\n"
        f"Password: {password}\n\n"
        f"Login: {login_url}\n"
        f"Please change your password after first login."
    )
    send_email(to=user.email, subject=subject, body=body)


# ── 1b. Password reset email (BRD v8 — forgot password) ──

def send_password_reset_email(user, token: str):
    locale = getattr(user, "locale", "vi")
    subject = _get_subject(locale, "password_reset")

    reset_url = f"http://{settings.BASE_DOMAIN}/auth/reset-password?token={token}"
    if getattr(user, "tenant", None):
        reset_url = f"http://{user.tenant.subdomain}.{settings.BASE_DOMAIN}/auth/reset-password?token={token}"

    body = (
        f"You requested a password reset.\n\n"
        f"Click the link below to reset your password (valid for 1 hour):\n"
        f"{reset_url}\n\n"
        f"If you did not request this, please ignore this email."
    )
    send_email(to=user.email, subject=subject, body=body)


# ── 2. Request confirmation (BRD #2 — user creates CHC) ──

def send_request_confirmation(user, req):
    locale = getattr(user, "locale", "vi")
    subject = _get_subject(locale, "request_confirmation", display_id=req.display_id)
    body = (
        f"Request {req.display_id} has been received.\n"
        f"Type: {req.type.value}\n"
        f"Status: {req.status.value}\n"
        f"We will process your request shortly."
    )
    send_email(to=user.email, subject=subject, body=body)


# ── 3. Admin notification (BRD #3 — new request) ──

def send_admin_new_request(admin, req):
    locale = getattr(admin, "locale", "vi")
    subject = _get_subject(locale, "admin_new_request", display_id=req.display_id)
    body = (
        f"New request {req.display_id} from user.\n"
        f"Type: {req.type.value}\n"
        f"Please review and assign an expert.\n\n"
        f"Admin portal: http://{settings.ADMIN_DOMAIN}/requests/{req.id}"
    )
    send_email(to=admin.email, subject=subject, body=body)


# ── 4. Expert assigned (BRD #4) ──

def send_expert_assigned(expert, req):
    locale = getattr(expert, "locale", "vi")
    subject = _get_subject(locale, "expert_assigned", display_id=req.display_id)
    body = (
        f"You have been assigned to process request {req.display_id}.\n"
        f"Type: {req.type.value}\n\n"
        f"Please download the ECUS file and upload your results.\n"
        f"Admin portal: http://{settings.ADMIN_DOMAIN}/requests/{req.id}"
    )
    send_email(to=expert.email, subject=subject, body=body)


# ── 5. Cancel notification (BRD #5) ──

def send_cancel_notification(db, req, notify_expert: bool = False):
    from app.models.user import User, UserRole

    # Notify admins
    admins = db.query(User).filter(
        User.tenant_id == req.tenant_id, User.role == UserRole.tenant_admin, User.is_active == True
    ).all()
    for admin in admins:
        locale = getattr(admin, "locale", "vi")
        subject = _get_subject(locale, "cancel_notification", display_id=req.display_id)
        send_email(to=admin.email, subject=subject, body=f"Request {req.display_id} has been cancelled by the user.")

    # Notify assigned expert if in processing
    if notify_expert and req.assigned_expert_id:
        expert = db.query(User).filter(User.id == req.assigned_expert_id).first()
        if expert:
            locale = getattr(expert, "locale", "vi")
            subject = _get_subject(locale, "cancel_notification", display_id=req.display_id)
            send_email(to=expert.email, subject=subject, body=f"Request {req.display_id} has been cancelled by the user.")


# ── 6. Result uploaded (BRD #6 — Expert uploads, Admin notified) ──

def send_result_uploaded_notification(db, req):
    from app.models.user import User, UserRole
    admins = db.query(User).filter(
        User.tenant_id == req.tenant_id, User.role == UserRole.tenant_admin, User.is_active == True
    ).all()
    for admin in admins:
        locale = getattr(admin, "locale", "vi")
        subject = _get_subject(locale, "result_uploaded", display_id=req.display_id)
        body = (
            f"Results for request {req.display_id} have been uploaded by the expert.\n"
            f"Please review and approve.\n\n"
            f"Admin portal: http://{settings.ADMIN_DOMAIN}/requests/{req.id}"
        )
        send_email(to=admin.email, subject=subject, body=body)


# ── 7. Result delivered (BRD #7 — Admin approves, User receives) ──

def send_result_delivered(db, req):
    from app.models.user import User
    from app.core import storage

    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        return

    # Generate download links for result files
    download_links = []
    for f in req.files:
        result_key = f.expert_s3_key or f.ai_s3_key
        if result_key:
            url = storage.generate_presigned_url(result_key)
            download_links.append(f"  - {f.original_filename}: {url}")

    links_text = "\n".join(download_links) if download_links else "  (No files available)"

    locale = getattr(user, "locale", "vi")
    subject = _get_subject(locale, "result_delivered", display_id=req.display_id)
    body = (
        f"Your request {req.display_id} has been completed!\n\n"
        f"Download your results (links valid for 7 days):\n{links_text}\n\n"
        f"You can also download from your dashboard."
    )
    send_email(to=user.email, subject=subject, body=body)


# ── 8. Expert reassignment (BRD v8) ──

def send_expert_reassigned(expert, req, removed: bool = False):
    locale = getattr(expert, "locale", "vi")
    key = "expert_reassigned_removed" if removed else "expert_reassigned_new"
    subject = _get_subject(locale, key, display_id=req.display_id)
    if removed:
        body = (
            f"Bạn đã được gỡ khỏi đơn {req.display_id}.\n"
            f"Đơn đã được chuyển cho chuyên viên khác."
        )
    else:
        body = (
            f"Bạn đã được chuyển giao xử lý đơn {req.display_id}.\n"
            f"Vui lòng kiểm tra và xử lý tại:\n"
            f"http://{settings.ADMIN_DOMAIN}/requests/{req.id}"
        )
    send_email(to=expert.email, subject=subject, body=body)


# ── 9. WP Draft ready (BRD v8 — AI completes, notify Admin) ──

def send_wp_draft_ready(db, req):
    from app.models.user import User, UserRole
    admins = db.query(User).filter(
        User.tenant_id == req.tenant_id, User.role == UserRole.tenant_admin, User.is_active == True
    ).all()
    for admin in admins:
        locale = getattr(admin, "locale", "vi")
        subject = _get_subject(locale, "wp_draft_ready", display_id=req.display_id)
        body = (
            f"WP Draft cho đơn {req.display_id} đã được AI xử lý xong.\n"
            f"Vui lòng assign Expert để hoàn thiện kết quả.\n\n"
            f"Admin portal: http://{settings.ADMIN_DOMAIN}/requests/{req.id}"
        )
        send_email(to=admin.email, subject=subject, body=body)


# ── 10. SLA Warning (BRD v8 — processing > 48h) ──

def send_sla_warning(db, req):
    from app.models.user import User, UserRole
    recipients = db.query(User).filter(
        User.tenant_id == req.tenant_id, User.is_active == True,
        User.role.in_([UserRole.tenant_admin, UserRole.expert]),
    ).all()
    filtered = [u for u in recipients if u.role == UserRole.tenant_admin or u.id == req.assigned_expert_id]
    for r in filtered:
        locale = getattr(r, "locale", "vi")
        subject = _get_subject(locale, "sla_warning", display_id=req.display_id)
        body = (
            f"Cảnh báo: đơn {req.display_id} đã quá 48h trong trạng thái processing.\n"
            f"Vui lòng kiểm tra và hoàn thiện kết quả."
        )
        send_email(to=r.email, subject=subject, body=body)


# ── 11. SLA Breach (BRD v8 — processing > 72h) ──

def send_sla_breach(db, req):
    from app.models.user import User, UserRole
    admins = db.query(User).filter(
        User.tenant_id == req.tenant_id, User.role == UserRole.tenant_admin, User.is_active == True
    ).all()
    for admin in admins:
        locale = getattr(admin, "locale", "vi")
        subject = _get_subject(locale, "sla_breach", display_id=req.display_id)
        body = (
            f"Vi phạm SLA: đơn {req.display_id} đã quá 72h.\n"
            f"Cần can thiệp khẩn cấp!"
        )
        send_email(to=admin.email, subject=subject, body=body)
