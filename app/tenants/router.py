from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import UserRole
from app.tenants import service
from app.tenants.schemas import TenantCreate, TenantUpdate, TenantResponse

router = APIRouter(tags=["tenants"])

super_admin_only = require_roles(UserRole.super_admin)


@router.get("", response_model=list[TenantResponse])
def get_tenants(db: Session = Depends(get_db), _=Depends(super_admin_only)):
    return service.get_all(db)


@router.post("", response_model=TenantResponse)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db), _=Depends(super_admin_only)):
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
    return {"message": "Tenant deleted"}
