from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.settings.schemas import EmailConfigResponse, EmailConfigUpdate, ProfileResponse, ProfileUpdate
from app.settings.service import get_email_config_masked, upsert_email_config

router = APIRouter(prefix="/settings", tags=["settings"])

tenant_admin_only = require_roles(UserRole.tenant_admin)


@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return ProfileResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role.value,
        username=current_user.username,
        locale=current_user.locale,
        company_name=current_user.company_name,
        tax_code=current_user.tax_code,
        company_address=current_user.company_address,
        contact_person=current_user.contact_person,
        phone=current_user.phone,
        contact_email=current_user.contact_email,
        industry=current_user.industry,
        company_type=current_user.company_type,
        is_first_login=current_user.is_first_login,
    )


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """F-U07: User updates personal/company info."""
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return get_profile(current_user)


@router.get("/email-config", response_model=EmailConfigResponse | None)
def get_email_config_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    return get_email_config_masked(db, current_user.tenant_id)


@router.put("/email-config", response_model=EmailConfigResponse)
def update_email_config_handler(
    payload: EmailConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    return upsert_email_config(db, current_user.tenant_id, payload.model_dump())
