from sqlalchemy.orm import Session

from app.models.tenant_email_config import TenantEmailConfig


def get_email_config(db: Session, tenant_id: int) -> TenantEmailConfig | None:
    return db.query(TenantEmailConfig).filter(TenantEmailConfig.tenant_id == tenant_id).first()


def get_email_config_masked(db: Session, tenant_id: int) -> TenantEmailConfig | None:
    """Returns config with password masked for GET response."""
    config = get_email_config(db, tenant_id)
    if config:
        config.smtp_password = "********"
    return config


def upsert_email_config(db: Session, tenant_id: int, data: dict) -> TenantEmailConfig:
    config = get_email_config(db, tenant_id)
    if config:
        for key, value in data.items():
            setattr(config, key, value)
    else:
        config = TenantEmailConfig(tenant_id=tenant_id, **data)
        db.add(config)
    db.commit()
    db.refresh(config)
    return config
