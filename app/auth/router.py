from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import blacklist_token
from app.core.config import settings
from app.auth import service
from app.auth.schemas import LoginRequest, TokenResponse, ResetPasswordRequest, ChangePasswordRequest
from app.models.user import User

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    token = service.login(db, payload)
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user)):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    blacklist_token(token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {"message": "Logged out"}


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
