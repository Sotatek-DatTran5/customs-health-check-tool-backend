from fastapi import Request, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import settings


async def tenant_middleware(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]

    # Admin site — bỏ qua tenant middleware
    if host == settings.ADMIN_DOMAIN:
        return await call_next(request)

    # User site — extract subdomain
    subdomain = host.replace(f".{settings.BASE_DOMAIN}", "")
    if not subdomain or subdomain == host:
        raise HTTPException(status_code=404, detail="Tenant not found")

    db: Session = SessionLocal()
    try:
        from app.models.tenant import Tenant
        tenant = db.query(Tenant).filter(
            Tenant.subdomain == subdomain,
            Tenant.is_active == True
        ).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        request.state.tenant_id = tenant.id
    finally:
        db.close()

    return await call_next(request)
