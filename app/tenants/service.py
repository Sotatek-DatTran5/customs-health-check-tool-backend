import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import email
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.tenants import repository as tenant_repo
from app.tenants.schemas import TenantCreate, TenantUpdate


def get_all(db: Session):
    return tenant_repo.get_all(db)


def get_by_id(db: Session, tenant_id: int):
    tenant = tenant_repo.get_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def create(db: Session, payload: TenantCreate):
    if tenant_repo.get_by_code(db, payload.tenant_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant code already exists")

    # 1. Create tenant
    tenant = tenant_repo.create(
        db,
        name=payload.name,
        tenant_code=payload.tenant_code.upper(),
        subdomain=payload.tenant_code.lower(),
        description=payload.description,
        is_active=payload.is_active,
    )

    # 2. Create tenant_admin user
    random_password = secrets.token_urlsafe(12)
    admin = User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        full_name=payload.admin_full_name,
        password_hash=hash_password(random_password),
        role=UserRole.tenant_admin,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    # 3. Send welcome email with credentials
    email.send_email(
        to=admin.email,
        subject=f"Welcome to CHC — Tenant {tenant.name}",
        body=(
            f"Your CHC tenant '{tenant.name}' has been created.\n\n"
            f"Admin account:\n"
            f"  Email:    {admin.email}\n"
            f"  Password: {random_password}\n\n"
            f"Login at: http://{settings.ADMIN_DOMAIN}/auth/login\n"
            f"Change your password at: http://{settings.ADMIN_DOMAIN}/auth/change-password"
        ),
    )

    return tenant


def update(db: Session, tenant_id: int, payload: TenantUpdate):
    tenant = get_by_id(db, tenant_id)
    return tenant_repo.update(db, tenant, **payload.model_dump(exclude_none=True))


def delete(db: Session, tenant_id: int):
    tenant = get_by_id(db, tenant_id)
    tenant_repo.soft_delete(db, tenant)
