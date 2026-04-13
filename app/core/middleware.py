from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import settings


def _is_ip_address(host: str) -> bool:
    parts = host.split(".")
    return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


async def tenant_middleware(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]

    # Admin site, base domain, or direct IP — skip tenant resolution
    if host in (settings.ADMIN_DOMAIN, settings.BASE_DOMAIN) or _is_ip_address(host):
        return await call_next(request)

    # User site — extract subdomain
    subdomain = host.replace(f".{settings.BASE_DOMAIN}", "")
    if not subdomain or subdomain == host:
        raise HTTPException(status_code=404, detail="Tenant not found")

    db: Session = SessionLocal()
    try:
        from app.models.tenant import Tenant
        tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # BRD v8 — Tenant disabled: return structured JSON with owner contact
        if not tenant.is_active:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "tenant_disabled",
                    "message": "Tenant này đã bị vô hiệu hóa. Vui lòng liên hệ chủ sở hữu.",
                    "tenant_name": tenant.name,
                    "owner_name": tenant.owner_name,
                    "owner_email": tenant.owner_email,
                    "owner_phone": tenant.owner_phone,
                },
            )
        request.state.tenant_id = tenant.id
    finally:
        db.close()

    return await call_next(request)
