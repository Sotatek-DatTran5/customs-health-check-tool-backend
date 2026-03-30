from sqlalchemy.orm import Session

from app.models.tenant import Tenant


def get_all(db: Session) -> list[Tenant]:
    return db.query(Tenant).all()


def get_by_id(db: Session, tenant_id: int) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def get_by_code(db: Session, tenant_code: str) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.tenant_code == tenant_code).first()


def create(db: Session, **kwargs) -> Tenant:
    tenant = Tenant(**kwargs)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def update(db: Session, tenant: Tenant, **kwargs) -> Tenant:
    for key, value in kwargs.items():
        if value is not None:
            setattr(tenant, key, value)
    db.commit()
    db.refresh(tenant)
    return tenant


def soft_delete(db: Session, tenant: Tenant):
    tenant.is_active = False
    db.commit()
