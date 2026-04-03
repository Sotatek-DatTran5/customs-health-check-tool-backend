from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.settings.schemas import EmailConfigResponse, EmailConfigUpdate, ProfileResponse
from app.settings.service import get_email_config, upsert_email_config

router = APIRouter(prefix="/settings", tags=["settings"])

tenant_admin_only = require_roles(UserRole.tenant_admin)


@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return ProfileResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role.value,
        username=current_user.username,
    )


@router.get("/email-config", response_model=EmailConfigResponse | None)
def get_email_config_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    config = get_email_config(db, current_user.tenant_id)
    return config


@router.put("/email-config", response_model=EmailConfigResponse)
def update_email_config_handler(
    payload: EmailConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    config = upsert_email_config(db, current_user.tenant_id, payload.model_dump())
    return config
