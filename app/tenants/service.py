from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.tenants import repository
from app.tenants.schemas import TenantCreate, TenantUpdate


def get_all(db: Session):
    return repository.get_all(db)


def get_by_id(db: Session, tenant_id: int):
    tenant = repository.get_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def create(db: Session, payload: TenantCreate):
    if repository.get_by_code(db, payload.tenant_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant code already exists")

    tenant = repository.create(
        db,
        name=payload.name,
        tenant_code=payload.tenant_code.upper(),
        subdomain=payload.tenant_code.lower(),
        description=payload.description,
        is_active=payload.is_active,
    )

    # TODO: tạo tenant_admin và gửi mail thông tin đăng nhập
    return tenant


def update(db: Session, tenant_id: int, payload: TenantUpdate):
    tenant = get_by_id(db, tenant_id)
    return repository.update(db, tenant, **payload.model_dump(exclude_none=True))


def delete(db: Session, tenant_id: int):
    tenant = get_by_id(db, tenant_id)
    repository.soft_delete(db, tenant)
