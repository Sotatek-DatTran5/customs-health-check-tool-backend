from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    validate_password_strength,
)
from app.auth import repository
from app.auth.schemas import LoginRequest, ResetPasswordRequest, ChangePasswordRequest
from app.models.user import User


def login(db: Session, payload: LoginRequest) -> dict:
    user = repository.get_user_by_email(db, payload.email)

    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # BRD 8.2 — Brute-force protection
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        raise HTTPException(status.HTTP_423_LOCKED, f"Account locked. Try again in {remaining} minutes.")

    if not verify_password(payload.password, user.password_hash):
        user.login_attempts = (user.login_attempts or 0) + 1
        if user.login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            user.login_attempts = 0
            db.commit()
            raise HTTPException(status.HTTP_423_LOCKED, f"Account locked for {settings.LOGIN_LOCKOUT_MINUTES} minutes after {settings.MAX_LOGIN_ATTEMPTS} failed attempts.")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")

    # Reset login attempts on success
    user.login_attempts = 0
    user.locked_until = None
    repository.update_last_login(db, user)

    token_data = {"user_id": user.id, "tenant_id": user.tenant_id, "role": user.role.value}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "is_first_login": user.is_first_login,
    }


def refresh_access_token(db: Session, refresh_token_str: str) -> dict:
    try:
        payload = decode_access_token(refresh_token_str)
        if payload.get("type") != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    user = repository.get_user_by_id(db, payload["user_id"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    token_data = {"user_id": user.id, "tenant_id": user.tenant_id, "role": user.role.value}
    return {"access_token": create_access_token(token_data)}


def reset_password(db: Session, payload: ResetPasswordRequest):
    error = validate_password_strength(payload.new_password)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)

    reset_token = repository.get_reset_token(db, payload.token)
    if not reset_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

    user = repository.get_user_by_id(db, reset_token.user_id)
    repository.update_password(db, user, hash_password(payload.new_password))
    repository.mark_reset_token_used(db, reset_token)


def change_password(db: Session, current_user: User, payload: ChangePasswordRequest):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Passwords do not match")

    error = validate_password_strength(payload.new_password)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")

    repository.update_password(db, current_user, hash_password(payload.new_password))
