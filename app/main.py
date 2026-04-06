from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.middleware import tenant_middleware
from app.auth.router import router as auth_router
from app.tenants.router import router as tenants_router
from app.users.router import router as users_router
from app.requests.router import router as requests_router
from app.dashboard.router import router as dashboard_router
from app.settings.router import router as settings_router

app = FastAPI(title="CHC Backend", version="1.0.0")

# CORS — restrict to valid domains (BRD 8.2)
allowed_origins = [
    f"http://{settings.ADMIN_DOMAIN}",
    f"https://{settings.ADMIN_DOMAIN}",
    f"http://*.{settings.BASE_DOMAIN}",
    f"https://*.{settings.BASE_DOMAIN}",
    "http://localhost:3000",  # Next.js dev
    "http://localhost:8329",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=tenant_middleware)

app.include_router(auth_router, prefix="/auth")
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(tenants_router, prefix="/tenants")
app.include_router(users_router, prefix="/users")
app.include_router(requests_router, prefix="/requests")
app.include_router(settings_router)


@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})
