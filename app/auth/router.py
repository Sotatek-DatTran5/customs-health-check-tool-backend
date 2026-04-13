from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import blacklist_token
from app.core.config import settings
from app.auth import service
from app.auth.schemas import LoginRequest, TokenResponse, RefreshTokenRequest, ResetPasswordRequest, ChangePasswordRequest, ForgotPasswordRequest
from app.models.user import User

router = APIRouter(tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    result = service.login(db, payload)
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    result = service.refresh_access_token(db, payload.refresh_token)
    return TokenResponse(access_token=result["access_token"])


@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user)):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    blacklist_token(token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {"message": "Logged out"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """BRD v8 — Self-service forgot password. Sends reset link via email. Always returns 200."""
    service.forgot_password(db, payload)
    return {"message": "Nếu email tồn tại trong hệ thống, chúng tôi đã gửi link đặt lại mật khẩu."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    service.reset_password(db, payload)
    return {"message": "Password reset successful"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.change_password(db, current_user, payload)
    return {"message": "Password changed successfully"}
