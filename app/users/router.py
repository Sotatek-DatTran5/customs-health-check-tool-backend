from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.users import service
from app.users.schemas import AdminCreateRequest, UserCreate, UserUpdate, UserResponse, OnboardingRequest, UpdateLocaleRequest

router = APIRouter()

tenant_admin_only = require_roles(UserRole.tenant_admin, UserRole.super_admin)
super_admin_only = require_roles(UserRole.super_admin)

USER_TAG = "User Site — Account"
ADMIN_TAG = "Admin Site — Users"
ADMIN_MGMT_TAG = "Admin Site — Admin Management"


# ── User self-service (must be before /{user_id} routes) ──

@router.post("/onboarding", response_model=UserResponse, tags=[USER_TAG])
def complete_onboarding(
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """F-U01: First login onboarding — fill company profile."""
    return service.complete_onboarding(db, current_user, payload)


@router.put("/locale", response_model=UserResponse, tags=[USER_TAG])
def update_locale(
    payload: UpdateLocaleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """F-U07: User changes display language."""
    return service.update_locale(db, current_user, payload.locale)


# ── F-A07: Admin management (Super Admin only — must be before /{user_id}) ──

@router.get("/admins/{tenant_id}", response_model=list[UserResponse], tags=[ADMIN_MGMT_TAG])
def list_admins_for_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    _=Depends(super_admin_only),
):
    """F-A07: Super Admin lists admins for a specific tenant."""
    return service.get_admins_for_tenant(db, tenant_id)


@router.post("/admins", response_model=UserResponse, tags=[ADMIN_MGMT_TAG])
def create_admin(
    payload: AdminCreateRequest,
    db: Session = Depends(get_db),
    _=Depends(super_admin_only),
):
    """F-A07: Super Admin creates admin for a tenant."""
    return service.create_admin(db, payload.tenant_id, payload.email, payload.full_name)


# ── Admin CRUD (Tenant Admin manages users in their tenant) ──

@router.get("", response_model=list[UserResponse], tags=[ADMIN_TAG])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    return service.get_all(db, current_user.tenant_id)


@router.post("", response_model=UserResponse, tags=[ADMIN_TAG])
def create_user(payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    """F-A04: Admin creates user (auto-gen password, send email)."""
    return service.create(db, payload, current_user.tenant_id)


@router.put("/{user_id}", response_model=UserResponse, tags=[ADMIN_TAG])
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    return service.update(db, user_id, payload, current_user.tenant_id)


@router.delete("/{user_id}", tags=[ADMIN_TAG])
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    service.delete(db, user_id, current_user.tenant_id)
    return {"message": "User deactivated"}


@router.post("/{user_id}/reset-password", tags=[ADMIN_TAG])
def reset_password(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    service.request_reset_password(db, user_id, current_user.tenant_id)
    return {"message": "Reset password email sent"}
