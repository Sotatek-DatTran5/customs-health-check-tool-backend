from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import UserRole
from app.tenants import service
from app.tenants.schemas import TenantCreate, TenantUpdate, TenantResponse, ExpertCreate, ExpertResponse

router = APIRouter(tags=["tenants"])

super_admin_only = require_roles(UserRole.super_admin)
admin_or_super = require_roles(UserRole.super_admin, UserRole.tenant_admin)


# ── Tenant CRUD (Super Admin) ──

@router.get("", response_model=list[TenantResponse])
def get_tenants(db: Session = Depends(get_db), _=Depends(super_admin_only)):
    return service.get_all(db)


@router.post("", response_model=TenantResponse)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db), _=Depends(super_admin_only)):
    """F-A06: Super Admin creates tenant + auto-creates admin."""
    return service.create(db, payload)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: int, db: Session = Depends(get_db), _=Depends(super_admin_only)):
    return service.get_by_id(db, tenant_id)


@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db), _=Depends(super_admin_only)):
    return service.update(db, tenant_id, payload)


@router.delete("/{tenant_id}")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db), _=Depends(super_admin_only)):
    service.delete(db, tenant_id)
    return {"message": "Tenant deactivated"}


@router.post("/{tenant_id}/logo", response_model=TenantResponse)
def upload_logo(tenant_id: int, logo: UploadFile = File(...), db: Session = Depends(get_db), _=Depends(super_admin_only)):
    """F-A06: Upload tenant logo to S3."""
    return service.upload_logo(db, tenant_id, logo)


# ── Expert management (BRD F-A05) ──

@router.get("/experts/all", response_model=list[ExpertResponse])
def get_experts(db: Session = Depends(get_db), _=Depends(admin_or_super)):
    """F-A05: List all experts (cross-tenant)."""
    return service.get_experts(db)


@router.post("/experts", response_model=ExpertResponse)
def create_expert(payload: ExpertCreate, db: Session = Depends(get_db), _=Depends(admin_or_super)):
    """F-A05: Create expert (cross-tenant)."""
    return service.create_expert(db, payload.email, payload.full_name)
