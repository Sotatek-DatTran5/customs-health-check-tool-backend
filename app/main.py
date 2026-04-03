from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.middleware import tenant_middleware
from app.auth.router import router as auth_router
from app.tenants.router import router as tenants_router
from app.users.router import router as users_router
from app.submissions.router import router as submissions_router
from app.dashboard.router import router as dashboard_router
from app.settings.router import router as settings_router

app = FastAPI(title="CHC Backend")

app.add_middleware(BaseHTTPMiddleware, dispatch=tenant_middleware)

app.include_router(auth_router, prefix="/auth")
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(tenants_router, prefix="/tenants")
app.include_router(users_router, prefix="/users")
app.include_router(submissions_router, prefix="/submissions")
app.include_router(settings_router)
