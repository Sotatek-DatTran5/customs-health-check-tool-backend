import random
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import email
from app.core.email_service import send_welcome_email
from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, UserRole
from app.users import repository
from app.users.schemas import UserCreate, UserUpdate, OnboardingRequest


VALID_LOCALES = {"vi", "en", "ko", "zh"}


def _generate_password(length: int = 12) -> str:
    """Generate a random password that satisfies BRD policy: 8+ chars, uppercase, lowercase, digit."""
    # Guarantee at least one of each required category
    mandatory = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    pool = string.ascii_letters + string.digits
    remaining = [secrets.choice(pool) for _ in range(length - len(mandatory))]
    chars = mandatory + remaining
    random.shuffle(chars)
    return "".join(chars)


def get_all(db: Session, tenant_id: int):
    return repository.get_all_in_tenant(db, tenant_id)


def get_by_id(db: Session, user_id: int, tenant_id: int) -> User:
    user = repository.get_by_id(db, user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


def create(db: Session, payload: UserCreate, tenant_id: int) -> User:
    """BRD F-A04 — Admin creates user. Auto-gen password, send email."""
    if repository.get_by_email(db, payload.email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already exists")

    password = payload.password or _generate_password()

    user = repository.create(
        db,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(password),
        role=payload.role,
        tenant_id=tenant_id,
    )

    # Get tenant name for welcome email
    tenant_name = user.tenant.name if user.tenant else "CHC"
    send_welcome_email(user, tenant_name, password)

    return user


def update(db: Session, user_id: int, payload: UserUpdate, tenant_id: int) -> User:
    user = get_by_id(db, user_id, tenant_id)
    return repository.update(db, user, **payload.model_dump(exclude_none=True))


def delete(db: Session, user_id: int, tenant_id: int):
    user = get_by_id(db, user_id, tenant_id)
    repository.soft_delete(db, user)


def complete_onboarding(db: Session, current_user: User, data: OnboardingRequest) -> User:
    """BRD F-U01 — First login: fill company profile, is_first_login → False."""
    current_user.company_name = data.company_name
    current_user.tax_code = data.tax_code
    current_user.company_address = data.company_address
    current_user.contact_person = data.contact_person
    current_user.phone = data.phone
    current_user.contact_email = data.contact_email or current_user.email
    current_user.industry = data.industry
    current_user.company_type = data.company_type
    current_user.is_first_login = False
    db.commit()
    db.refresh(current_user)
    return current_user


def update_locale(db: Session, current_user: User, locale: str) -> User:
    if locale not in VALID_LOCALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid locale. Valid: {VALID_LOCALES}")
    current_user.locale = locale
    db.commit()
    db.refresh(current_user)
    return current_user


# ── F-A07: Admin management (Super Admin) ──

def get_admins_for_tenant(db: Session, tenant_id: int) -> list[User]:
    """List all tenant_admin users for a specific tenant."""
    return db.query(User).filter(
        User.tenant_id == tenant_id, User.role == UserRole.tenant_admin
    ).all()


def create_admin(db: Session, tenant_id: int, admin_email: str, full_name: str) -> User:
    """BRD F-A07 — Super Admin creates admin for a tenant."""
    if repository.get_by_email(db, admin_email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already exists")

    # Verify tenant exists
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")

    password = _generate_password()
    admin = repository.create(
        db,
        email=admin_email,
        full_name=full_name,
        password_hash=hash_password(password),
        role=UserRole.tenant_admin,
        tenant_id=tenant_id,
    )
    send_welcome_email(admin, tenant.name, password)
    return admin


def request_reset_password(db: Session, user_id: int, tenant_id: int):
    user = get_by_id(db, user_id, tenant_id)

    from jose import jwt
    token_data = {
        "user_id": user.id,
        "email": user.email,
        "jti": secrets.token_urlsafe(16),
    }
    reset_token_str = jwt.encode(token_data, settings.SECRET_KEY, algorithm="HS256")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    reset_record = PasswordResetToken(
        user_id=user.id,
        token=reset_token_str,
        expires_at=expires_at,
    )
    db.add(reset_record)
    db.commit()

    reset_url = f"http://{settings.BASE_DOMAIN}/auth/reset-password?token={reset_token_str}"
    email.send_email(
        to=user.email,
        subject="CHC — Password Reset",
        body=(
            f"Hi {user.full_name},\n\n"
            f"Click to reset your password (valid {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n"
            f"{reset_url}\n\n"
            f"If you didn't request this, please ignore."
        ),
    )
