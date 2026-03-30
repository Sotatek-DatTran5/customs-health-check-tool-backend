from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.users import service
from app.users.schemas import UserCreate, UserUpdate, UserResponse

router = APIRouter(tags=["users"])

tenant_admin_only = require_roles(UserRole.tenant_admin)


@router.get("", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    return service.get_all(db, current_user.tenant_id)


@router.post("", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    return service.create(db, payload, current_user.tenant_id)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    return service.update(db, user_id, payload, current_user.tenant_id)


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    service.delete(db, user_id, current_user.tenant_id)
    return {"message": "User deleted"}


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    service.request_reset_password(db, user_id, current_user.tenant_id)
    return {"message": "Reset password email sent"}
