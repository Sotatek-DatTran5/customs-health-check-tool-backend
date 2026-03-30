from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.dashboard import service
from app.dashboard.schemas import DashboardStats

router = APIRouter(tags=["dashboard"])

allowed_roles = require_roles(UserRole.super_admin, UserRole.tenant_admin, UserRole.expert)


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(allowed_roles)):
    return service.get_stats(db, current_user)
