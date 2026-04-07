from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.email_service import send_welcome_email
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.users.service import _generate_password
from app.tenants import repository as tenant_repo
from app.tenants.schemas import TenantCreate, TenantUpdate


def get_all(db: Session):
    return tenant_repo.get_all(db)


def get_by_id(db: Session, tenant_id: int):
    tenant = tenant_repo.get_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return tenant


def create(db: Session, payload: TenantCreate):
    if tenant_repo.get_by_code(db, payload.tenant_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tenant code already exists")

    tenant = tenant_repo.create(
        db,
        name=payload.name,
        tenant_code=payload.tenant_code.upper(),
        subdomain=payload.tenant_code.lower(),
        description=payload.description,
        is_active=payload.is_active,
        primary_color=payload.primary_color,
        display_name=payload.display_name or payload.name,
        etariff_daily_limit=payload.etariff_daily_limit,
    )

    # Create tenant_admin
    random_password = _generate_password()
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

    send_welcome_email(admin, tenant.name, random_password)
    return tenant


def update(db: Session, tenant_id: int, payload: TenantUpdate):
    tenant = get_by_id(db, tenant_id)
    return tenant_repo.update(db, tenant, **payload.model_dump(exclude_none=True))


def delete(db: Session, tenant_id: int):
    tenant = get_by_id(db, tenant_id)
    tenant_repo.soft_delete(db, tenant)


def upload_logo(db: Session, tenant_id: int, logo_file: UploadFile):
    """Upload tenant logo to S3."""
    tenant = get_by_id(db, tenant_id)
    s3_key = f"tenants/{tenant_id}/logo/{logo_file.filename}"
    content = logo_file.file.read()
    storage.upload_file(s3_key, content, logo_file.content_type or "image/png")
    tenant.logo_s3_key = s3_key
    db.commit()
    db.refresh(tenant)
    return tenant


# ── Expert management (BRD F-A05) ──

def get_experts(db: Session) -> list[User]:
    """Get all experts (cross-tenant)."""
    return db.query(User).filter(User.role == UserRole.expert, User.is_active == True).all()


def create_expert(db: Session, email: str, full_name: str) -> User:
    """Create expert (no tenant — cross-tenant access)."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already exists")

    random_password = _generate_password()
    expert = User(
        tenant_id=None,
        email=email,
        full_name=full_name,
        password_hash=hash_password(random_password),
        role=UserRole.expert,
    )
    db.add(expert)
    db.commit()
    db.refresh(expert)

    send_welcome_email(expert, "CHC Platform", random_password)
    return expert
