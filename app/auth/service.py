from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import verify_password, create_access_token, hash_password
from app.auth import repository
from app.auth.schemas import LoginRequest, ResetPasswordRequest, ChangePasswordRequest
from app.models.user import User


def login(db: Session, payload: LoginRequest) -> str:
    user = repository.get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    repository.update_last_login(db, user)

    token = create_access_token({"user_id": user.id, "tenant_id": user.tenant_id, "role": user.role})
    return token


def reset_password(db: Session, payload: ResetPasswordRequest):
    reset_token = repository.get_reset_token(db, payload.token)
    if not reset_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    user = repository.get_user_by_id(db, reset_token.user_id)
    repository.update_password(db, user, hash_password(payload.new_password))
    repository.mark_reset_token_used(db, reset_token)


def change_password(db: Session, current_user: User, payload: ChangePasswordRequest):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    repository.update_password(db, current_user, hash_password(payload.new_password))
