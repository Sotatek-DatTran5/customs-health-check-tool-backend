from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import email
from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.users import repository
from app.users.schemas import UserCreate, UserUpdate
from app.models.user import User


def get_all(db: Session, tenant_id: int):
    return repository.get_all_in_tenant(db, tenant_id)


def get_by_id(db: Session, user_id: int, tenant_id: int) -> User:
    user = repository.get_by_id(db, user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def create(db: Session, payload: UserCreate, tenant_id: int) -> User:
    if repository.get_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    return repository.create(
        db,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        tenant_id=tenant_id,
    )


def update(db: Session, user_id: int, payload: UserUpdate, tenant_id: int) -> User:
    user = get_by_id(db, user_id, tenant_id)
    return repository.update(db, user, **payload.model_dump(exclude_none=True))


def delete(db: Session, user_id: int, tenant_id: int):
    user = get_by_id(db, user_id, tenant_id)
    repository.soft_delete(db, user)


def request_reset_password(db: Session, user_id: int, tenant_id: int):
    user = get_by_id(db, user_id, tenant_id)

    # Generate reset token
    from jose import jwt
    import secrets

    token_data = {
        "user_id": user.id,
        "email": user.email,
        "jti": secrets.token_urlsafe(16),
    }
    reset_token_str = jwt.encode(
        token_data,
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    reset_record = PasswordResetToken(
        user_id=user.id,
        token=reset_token_str,
        expires_at=expires_at,
    )
    db.add(reset_record)
    db.commit()

    # Send reset email
    reset_url = f"http://{settings.BASE_DOMAIN}/auth/reset-password?token={reset_token_str}"
    email.send_email(
        to=user.email,
        subject="CHC — Password Reset Request",
        body=(
            f"Hi {user.full_name},\n\n"
            f"A password reset was requested for your CHC account ({user.email}).\n\n"
            f"Click the link below to reset your password (valid for {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n"
            f"{reset_url}\n\n"
            f"If you didn't request this, please ignore this email."
        ),
    )
