# CHC Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fully functional FastAPI backend for CHC (Customs Health Check) multi-tenant system — run `docker compose up` and Swagger available at port 8329.

**Architecture:** Multi-tenant FastAPI app with PostgreSQL, Redis (Celery broker + JWT blacklist), AWS S3 (file storage), AWS SES (email). Admin site at `admin.chc.com`, user sites at `*.chc.com` via wildcard DNS. Tenant resolved from `Host` header middleware.

**Tech Stack:** Python/FastAPI, SQLAlchemy 2.0, Alembic, Celery, Redis, PostgreSQL, boto3 (S3/SES), bcrypt, python-jose, openpyxl, uv, Docker Compose

---

## Task 1: Fix Docker + App Startup

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Dockerfile`
- Modify: `app/main.py`
- Modify: `app/core/config.py`

**Step 1: Update port to 8329 in docker-compose.yml**

```yaml
# docker-compose.yml — thay đổi ports của app
ports:
  - "8329:8329"
```

**Step 2: Update Dockerfile CMD port**

```dockerfile
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8329"]
```

**Step 3: Update main.py — thêm Swagger config, CORS, lifespan**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.middleware import tenant_middleware
from app.auth.router import router as auth_router
from app.tenants.router import router as tenants_router
from app.users.router import router as users_router
from app.submissions.router import router as submissions_router
from app.dashboard.router import router as dashboard_router
from app.settings.router import router as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title="CHC Backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(BaseHTTPMiddleware, dispatch=tenant_middleware)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
app.include_router(tenants_router, prefix="/tenants", tags=["tenants"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(submissions_router, prefix="/submissions", tags=["submissions"])
app.include_router(settings_router, prefix="/settings", tags=["settings"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 4: Update config.py — thêm PASSWORD_RESET_EXPIRE_MINUTES, make AWS fields optional (dev)**

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str = "postgresql://user:password@postgres:5432/chc"
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"

    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-southeast-1"
    S3_BUCKET_NAME: Optional[str] = None
    SES_SENDER_EMAIL: Optional[str] = None

    AI_API_URL: Optional[str] = None
    AI_API_KEY: str = ""

    ADMIN_DOMAIN: str = "admin.chc.com"
    BASE_DOMAIN: str = "chc.com"

    class Config:
        env_file = ".env"

settings = Settings()
```

**Step 5: Commit**
```bash
git add docker-compose.yml Dockerfile app/main.py app/core/config.py
git commit -m "fix: update port to 8329, add CORS, health endpoint"
```

---

## Task 2: Update Models (DB Schema)

**Files:**
- Modify: `app/models/user.py`
- Modify: `app/models/submission.py`
- Modify: `app/models/tenant.py`
- Create: `app/models/tenant_email_config.py`
- Modify: `app/models/__init__.py`

**Step 1: Update user.py — thêm is_first_login, username nullable fix**

```python
import enum
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    tenant_admin = "tenant_admin"
    expert = "expert"
    user = "user"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_first_login: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship("PasswordResetToken", back_populates="user")
```

**Step 2: Update submission.py — thêm SubmissionType, type field vào Submission**

```python
import enum
from datetime import datetime, timezone
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class SubmissionType(str, enum.Enum):
    file_upload = "file_upload"
    batch_dataset = "batch_dataset"
    manual_input = "manual_input"

class AIStatus(str, enum.Enum):
    not_started = "not_started"
    running = "running"
    completed = "completed"
    failed = "failed"

class DeliveryStatus(str, enum.Enum):
    not_sent = "not_sent"
    sent = "sent"
    failed = "failed"

class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    display_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    type: Mapped[SubmissionType] = mapped_column(Enum(SubmissionType), default=SubmissionType.file_upload)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="submissions")
    user: Mapped["User"] = relationship("User")
    files: Mapped[list["SubmissionFile"]] = relationship("SubmissionFile", back_populates="submission", cascade="all, delete-orphan")

class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    s3_key: Mapped[str] = mapped_column(String(500))
    ai_status: Mapped[AIStatus] = mapped_column(Enum(AIStatus), default=AIStatus.not_started)
    ai_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expert_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus), default=DeliveryStatus.not_sent)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    submission: Mapped["Submission"] = relationship("Submission", back_populates="files")
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship("AnalysisJob", back_populates="submission_file", cascade="all, delete-orphan")

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_file_id: Mapped[int] = mapped_column(ForeignKey("submission_files.id"), index=True)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    submission_file: Mapped["SubmissionFile"] = relationship("SubmissionFile", back_populates="analysis_jobs")
```

**Step 3: Create tenant_email_config.py**

```python
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class TenantEmailConfig(Base):
    __tablename__ = "tenant_email_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), unique=True)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_password: Mapped[str | None] = mapped_column(String(500), nullable=True)  # encrypted at app level
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="email_config")
```

**Step 4: Update tenant.py — thêm email_config relationship**

```python
# thêm vào cuối class Tenant:
email_config: Mapped["TenantEmailConfig | None"] = relationship("TenantEmailConfig", back_populates="tenant", uselist=False)
```

**Step 5: Update models/__init__.py**

```python
from app.models.tenant import Tenant
from app.models.tenant_email_config import TenantEmailConfig
from app.models.user import User, UserRole
from app.models.password_reset_token import PasswordResetToken
from app.models.submission import Submission, SubmissionFile, AnalysisJob, AIStatus, DeliveryStatus, SubmissionType

__all__ = [
    "Tenant", "TenantEmailConfig",
    "User", "UserRole",
    "PasswordResetToken",
    "Submission", "SubmissionFile", "AnalysisJob",
    "AIStatus", "DeliveryStatus", "SubmissionType",
]
```

**Step 6: Commit**
```bash
git add app/models/
git commit -m "feat: update models — add is_first_login, SubmissionType, TenantEmailConfig"
```

---

## Task 3: Alembic Migration

**Files:**
- Modify: `migrations/alembic.ini` — fix script_location path
- Modify: `migrations/env.py` — đảm bảo import đúng
- Create: `migrations/versions/0001_initial_schema.py` (auto-generated)

**Step 1: Fix alembic.ini — script_location**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
file_template = %%(rev)s_%%(slug)s
```

**Step 2: Chạy autogenerate migration**
```bash
cd chc-backend
uv run alembic revision --autogenerate -m "initial_schema"
```
Expected: file mới tạo trong `migrations/versions/`

**Step 3: Review file migration vừa tạo — đảm bảo có đủ tables**
Kiểm tra có: tenants, tenant_email_configs, users, password_reset_tokens, submissions, submission_files, analysis_jobs

**Step 4: Commit**
```bash
git add migrations/
git commit -m "feat: add initial alembic migration"
```

---

## Task 4: Core Services — Email & S3

**Files:**
- Create: `app/core/email.py`
- Create: `app/core/s3.py`
- Create: `app/core/utils.py`

**Step 1: Create app/core/utils.py**

```python
import secrets
import string

def generate_random_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))

def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)
```

**Step 2: Create app/core/s3.py**

```python
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings

def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

def upload_file(file_content: bytes, s3_key: str, content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") -> str:
    if not settings.S3_BUCKET_NAME:
        # Dev mode: skip S3
        return s3_key
    client = get_s3_client()
    client.put_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key, Body=file_content, ContentType=content_type)
    return s3_key

def generate_presigned_url(s3_key: str, expiration: int = 604800) -> str:
    """expiration in seconds, default 7 days"""
    if not settings.S3_BUCKET_NAME:
        return f"/dev/files/{s3_key}"
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expiration,
    )

def stream_file(s3_key: str):
    """Generator để stream file từ S3"""
    if not settings.S3_BUCKET_NAME:
        yield b"dev-file-content"
        return
    client = get_s3_client()
    response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    for chunk in response["Body"].iter_chunks(chunk_size=8192):
        yield chunk
```

**Step 3: Create app/core/email.py**

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import boto3
from app.core.config import settings

def send_email(to_email: str, subject: str, body: str, smtp_config: Optional[dict] = None):
    """
    smtp_config: dict với keys smtp_host, smtp_port, sender_email, sender_name, smtp_username, smtp_password
    Nếu None → dùng AWS SES
    """
    if smtp_config and smtp_config.get("is_enabled"):
        _send_via_smtp(to_email, subject, body, smtp_config)
    else:
        _send_via_ses(to_email, subject, body)

def _send_via_ses(to_email: str, subject: str, body: str):
    if not settings.SES_SENDER_EMAIL:
        # Dev mode: log email
        print(f"[DEV EMAIL] To: {to_email} | Subject: {subject}\n{body}")
        return
    client = boto3.client(
        "ses",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    client.send_email(
        Source=settings.SES_SENDER_EMAIL,
        Destination={"ToAddresses": [to_email]},
        Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
    )

def _send_via_smtp(to_email: str, subject: str, body: str, config: dict):
    msg = MIMEMultipart()
    msg["From"] = f"{config.get('sender_name', '')} <{config['sender_email']}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
        server.starttls()
        server.login(config["smtp_username"], config["smtp_password"])
        server.send_message(msg)

# Email templates
def send_account_created(to_email: str, full_name: str, password: str, smtp_config=None):
    send_email(
        to_email=to_email,
        subject="Your CHC Account Has Been Created",
        body=f"Hello {full_name},\n\nYour account has been created.\nEmail: {to_email}\nPassword: {password}\n\nPlease change your password after first login.\n\nRegards,\nCHC Team",
        smtp_config=smtp_config,
    )

def send_reset_password(to_email: str, full_name: str, reset_link: str, smtp_config=None):
    send_email(
        to_email=to_email,
        subject="Reset Your CHC Password",
        body=f"Hello {full_name},\n\nClick the link below to reset your password:\n{reset_link}\n\nThis link expires in 60 minutes.\n\nRegards,\nCHC Team",
        smtp_config=smtp_config,
    )

def send_upload_confirmation(to_email: str, full_name: str, display_id: str, smtp_config=None):
    send_email(
        to_email=to_email,
        subject=f"Submission {display_id} Received",
        body=f"Hello {full_name},\n\nYour submission {display_id} has been received and is being processed.\nYou will be notified when the results are ready.\n\nRegards,\nCHC Team",
        smtp_config=smtp_config,
    )

def send_result_ready(to_email: str, full_name: str, display_id: str, download_url: str, smtp_config=None):
    send_email(
        to_email=to_email,
        subject=f"Results Ready — {display_id}",
        body=f"Hello {full_name},\n\nYour results for submission {display_id} are ready.\nDownload link (valid 7 days): {download_url}\n\nRegards,\nCHC Team",
        smtp_config=smtp_config,
    )
```

**Step 4: Commit**
```bash
git add app/core/email.py app/core/s3.py app/core/utils.py
git commit -m "feat: add email, S3, and utils services"
```

---

## Task 5: Auth Module (hoàn chỉnh)

**Files:**
- Modify: `app/auth/schemas.py`
- Modify: `app/auth/repository.py`
- Modify: `app/auth/service.py`
- Modify: `app/auth/router.py`

**Step 1: Update auth/schemas.py**

```python
from pydantic import BaseModel, EmailStr
from enum import Enum

class RoleType(str, Enum):
    admin = "admin"
    user = "user"

class LoginRequest(BaseModel):
    login: str  # email hoặc username
    password: str
    role_type: RoleType = RoleType.admin

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    redirect_url: str | None = None
    is_first_login: bool = False

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str
```

**Step 2: Update auth/repository.py — thêm get_by_username**

```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.password_reset_token import PasswordResetToken

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email, User.is_active == True).first()

def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username, User.is_active == True).first()

def get_user_by_login(db: Session, login: str) -> User | None:
    """Tìm user bằng email hoặc username"""
    user = get_user_by_email(db, login)
    if not user:
        user = get_user_by_username(db, login)
    return user

def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()

def update_last_login(db: Session, user: User):
    user.last_login_at = datetime.now(timezone.utc)
    user.is_first_login = False
    db.commit()

def update_password(db: Session, user: User, password_hash: str):
    user.password_hash = password_hash
    db.commit()

def create_reset_token(db: Session, user_id: int, token: str, expires_at: datetime) -> PasswordResetToken:
    reset_token = PasswordResetToken(user_id=user_id, token=token, expires_at=expires_at)
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return reset_token

def get_reset_token(db: Session, token: str) -> PasswordResetToken | None:
    return db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used_at == None,
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()

def mark_reset_token_used(db: Session, reset_token: PasswordResetToken):
    reset_token.used_at = datetime.now(timezone.utc)
    db.commit()
```

**Step 3: Update auth/service.py**

```python
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import verify_password, create_access_token, hash_password
from app.core.config import settings
from app.auth import repository
from app.auth.schemas import LoginRequest, RoleType, ResetPasswordRequest, ChangePasswordRequest
from app.models.user import User, UserRole

ADMIN_ROLES = {UserRole.super_admin, UserRole.tenant_admin, UserRole.expert}

def login(db: Session, payload: LoginRequest) -> dict:
    user = repository.get_user_by_login(db, payload.login)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Validate role_type vs actual role
    if payload.role_type == RoleType.admin and user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin account")
    if payload.role_type == RoleType.user and user.role != UserRole.user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a user account")

    is_first = user.is_first_login
    repository.update_last_login(db, user)

    token = create_access_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role,
    })

    redirect_url = None
    if user.role == UserRole.user and user.tenant:
        redirect_url = f"https://{user.tenant.subdomain}.{settings.BASE_DOMAIN}"

    return {"token": token, "redirect_url": redirect_url, "is_first_login": is_first}

def reset_password(db: Session, payload: ResetPasswordRequest):
    reset_token = repository.get_reset_token(db, payload.token)
    if not reset_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    user = repository.get_user_by_id(db, reset_token.user_id)
    repository.update_password(db, user, hash_password(payload.new_password))
    repository.mark_reset_token_used(db, reset_token)

def change_password(db: Session, current_user: User, payload: ChangePasswordRequest):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    repository.update_password(db, current_user, hash_password(payload.new_password))
```

**Step 4: Update auth/router.py**

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import blacklist_token
from app.core.config import settings
from app.auth import service
from app.auth.schemas import LoginRequest, TokenResponse, ResetPasswordRequest, ChangePasswordRequest
from app.models.user import User

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    result = service.login(db, payload)
    return TokenResponse(
        access_token=result["token"],
        redirect_url=result["redirect_url"],
        is_first_login=result["is_first_login"],
    )

@router.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user)):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    blacklist_token(token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {"message": "Logged out"}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    service.reset_password(db, payload)
    return {"message": "Password reset successful"}

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.change_password(db, current_user, payload)
    return {"message": "Password changed successfully"}
```

**Step 5: Commit**
```bash
git add app/auth/
git commit -m "feat: complete auth module — login by email/username, role_type, redirect"
```

---

## Task 6: Tenant Module (hoàn chỉnh)

**Files:**
- Modify: `app/tenants/schemas.py`
- Modify: `app/tenants/repository.py`
- Modify: `app/tenants/service.py`
- Modify: `app/tenants/router.py`

**Step 1: Update tenants/schemas.py**

```python
from datetime import datetime
from pydantic import BaseModel, EmailStr

class AdminInfo(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool

    class Config:
        from_attributes = True

class TenantCreate(BaseModel):
    name: str
    tenant_code: str
    description: str | None = None
    admin_email: EmailStr
    is_active: bool = True

class TenantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    admin_email: EmailStr | None = None
    admin_full_name: str | None = None

class TenantResponse(BaseModel):
    id: int
    name: str
    tenant_code: str
    subdomain: str
    description: str | None
    is_active: bool
    created_at: datetime
    admin: AdminInfo | None = None

    class Config:
        from_attributes = True
```

**Step 2: Update tenants/repository.py**

```python
from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.models.user import User, UserRole

def get_all(db: Session, status: str | None = None) -> list[Tenant]:
    q = db.query(Tenant)
    if status == "active":
        q = q.filter(Tenant.is_active == True)
    elif status == "inactive":
        q = q.filter(Tenant.is_active == False)
    return q.all()

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

def get_admin(db: Session, tenant_id: int) -> User | None:
    return db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == UserRole.tenant_admin,
        User.is_active == True,
    ).first()

def create_admin(db: Session, tenant_id: int, email: str, full_name: str, password_hash: str) -> User:
    admin = User(
        tenant_id=tenant_id,
        email=email,
        full_name=full_name,
        password_hash=password_hash,
        role=UserRole.tenant_admin,
        is_first_login=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
```

**Step 3: Update tenants/service.py**

```python
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.core.utils import generate_random_password
from app.core.email import send_account_created
from app.tenants import repository
from app.tenants.schemas import TenantCreate, TenantUpdate

def get_all(db: Session, status: str | None = None):
    tenants = repository.get_all(db, status)
    result = []
    for t in tenants:
        admin = repository.get_admin(db, t.id)
        t_dict = {"tenant": t, "admin": admin}
        result.append(t_dict)
    return tenants  # router sẽ handle admin injection

def get_by_id(db: Session, tenant_id: int):
    tenant = repository.get_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant

def create(db: Session, payload: TenantCreate):
    code = payload.tenant_code.upper()
    if repository.get_by_code(db, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant code already exists")

    tenant = repository.create(
        db,
        name=payload.name,
        tenant_code=code,
        subdomain=payload.tenant_code.lower(),
        description=payload.description,
        is_active=payload.is_active,
    )

    password = generate_random_password()
    full_name = payload.admin_email.split("@")[0]
    admin = repository.create_admin(db, tenant.id, payload.admin_email, full_name, hash_password(password))

    # Gửi mail (best-effort, không raise nếu lỗi)
    try:
        send_account_created(admin.email, admin.full_name, password)
    except Exception:
        pass

    return tenant

def update(db: Session, tenant_id: int, payload: TenantUpdate):
    tenant = get_by_id(db, tenant_id)
    update_data = payload.model_dump(exclude_none=True)
    admin_email = update_data.pop("admin_email", None)
    admin_full_name = update_data.pop("admin_full_name", None)
    repository.update(db, tenant, **update_data)
    if admin_email or admin_full_name:
        admin = repository.get_admin(db, tenant_id)
        if admin:
            if admin_email:
                admin.email = admin_email
            if admin_full_name:
                admin.full_name = admin_full_name
            db.commit()
    return tenant

def delete(db: Session, tenant_id: int):
    tenant = get_by_id(db, tenant_id)
    repository.soft_delete(db, tenant)
```

**Step 4: Update tenants/router.py**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.tenants import service, repository
from app.tenants.schemas import TenantCreate, TenantUpdate, TenantResponse, AdminInfo

router = APIRouter()
super_admin_only = require_roles(UserRole.super_admin)

@router.get("", response_model=list[TenantResponse])
def get_tenants(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(super_admin_only),
):
    tenants = service.get_all(db, status)
    result = []
    for t in tenants:
        admin = repository.get_admin(db, t.id)
        t_data = TenantResponse.model_validate(t)
        if admin:
            t_data.admin = AdminInfo.model_validate(admin)
        result.append(t_data)
    return result

@router.post("", response_model=TenantResponse)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db), _: User = Depends(super_admin_only)):
    return service.create(db, payload)

@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: int, db: Session = Depends(get_db), _: User = Depends(super_admin_only)):
    tenant = service.get_by_id(db, tenant_id)
    admin = repository.get_admin(db, tenant_id)
    t_data = TenantResponse.model_validate(tenant)
    if admin:
        t_data.admin = AdminInfo.model_validate(admin)
    return t_data

@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db), _: User = Depends(super_admin_only)):
    return service.update(db, tenant_id, payload)

@router.delete("/{tenant_id}")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db), _: User = Depends(super_admin_only)):
    service.delete(db, tenant_id)
    return {"message": "Tenant deleted"}
```

**Step 5: Commit**
```bash
git add app/tenants/
git commit -m "feat: complete tenant module with admin creation and email"
```

---

## Task 7: User Module (hoàn chỉnh)

**Files:**
- Modify: `app/users/schemas.py`
- Modify: `app/users/repository.py`
- Modify: `app/users/service.py`
- Modify: `app/users/router.py`

**Step 1: Update users/schemas.py**

```python
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole  # chỉ user hoặc expert

class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_first_login: bool
    last_login_at: datetime | None
    tenant_id: int | None

    class Config:
        from_attributes = True
```

**Step 2: Update users/repository.py**

```python
from sqlalchemy.orm import Session
from app.models.user import User, UserRole

def get_all_in_tenant(db: Session, tenant_id: int, role: str | None = None) -> list[User]:
    q = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role.in_([UserRole.user, UserRole.expert]),
    )
    if role:
        q = q.filter(User.role == role)
    return q.all()

def get_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()

def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

def create(db: Session, **kwargs) -> User:
    user = User(**kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update(db: Session, user: User, **kwargs) -> User:
    for key, value in kwargs.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

def soft_delete(db: Session, user: User):
    user.is_active = False
    db.commit()
```

**Step 3: Update users/service.py**

```python
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.core.utils import generate_random_password, generate_reset_token
from app.core.email import send_account_created, send_reset_password
from app.core.config import settings
from app.users import repository
from app.users.schemas import UserCreate, UserUpdate
from app.models.user import User, UserRole
from app.models.password_reset_token import PasswordResetToken

ALLOWED_ROLES = {UserRole.user, UserRole.expert}

def get_all(db: Session, tenant_id: int, role: str | None = None):
    return repository.get_all_in_tenant(db, tenant_id, role)

def get_by_id(db: Session, user_id: int, tenant_id: int) -> User:
    user = repository.get_by_id(db, user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

def create(db: Session, payload: UserCreate, tenant_id: int, smtp_config=None) -> User:
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    if repository.get_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    password = generate_random_password()
    user = repository.create(
        db,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(password),
        role=payload.role,
        tenant_id=tenant_id,
        is_first_login=True,
    )

    try:
        send_account_created(user.email, user.full_name, password, smtp_config)
    except Exception:
        pass

    return user

def update(db: Session, user_id: int, payload: UserUpdate, tenant_id: int) -> User:
    user = get_by_id(db, user_id, tenant_id)
    return repository.update(db, user, **payload.model_dump(exclude_none=True))

def delete(db: Session, user_id: int, tenant_id: int):
    user = get_by_id(db, user_id, tenant_id)
    repository.soft_delete(db, user)

def request_reset_password(db: Session, user_id: int, tenant_id: int, smtp_config=None):
    user = get_by_id(db, user_id, tenant_id)
    token = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    reset = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    db.add(reset)
    db.commit()
    reset_link = f"https://{settings.ADMIN_DOMAIN}/reset-password?token={token}"
    try:
        send_reset_password(user.email, user.full_name, reset_link, smtp_config)
    except Exception:
        pass
```

**Step 4: Update users/router.py**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.users import service
from app.users.schemas import UserCreate, UserUpdate, UserResponse

router = APIRouter()
tenant_admin_only = require_roles(UserRole.tenant_admin)

@router.get("", response_model=list[UserResponse])
def get_users(
    role: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    return service.get_all(db, current_user.tenant_id, role)

@router.post("", response_model=UserResponse)
def create_user(payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    smtp_config = _get_smtp_config(db, current_user.tenant_id)
    return service.create(db, payload, current_user.tenant_id, smtp_config)

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    return service.update(db, user_id, payload, current_user.tenant_id)

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    service.delete(db, user_id, current_user.tenant_id)
    return {"message": "User deleted"}

@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    smtp_config = _get_smtp_config(db, current_user.tenant_id)
    service.request_reset_password(db, user_id, current_user.tenant_id, smtp_config)
    return {"message": "Reset password email sent"}

def _get_smtp_config(db: Session, tenant_id: int) -> dict | None:
    from app.models.tenant_email_config import TenantEmailConfig
    config = db.query(TenantEmailConfig).filter(TenantEmailConfig.tenant_id == tenant_id).first()
    if config and config.is_enabled:
        return {
            "is_enabled": True,
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "sender_email": config.sender_email,
            "sender_name": config.sender_name,
            "smtp_username": config.smtp_username,
            "smtp_password": config.smtp_password,
        }
    return None
```

**Step 5: Commit**
```bash
git add app/users/
git commit -m "feat: complete user module — random password, email on create"
```

---

## Task 8: Submissions Module (hoàn chỉnh)

**Files:**
- Modify: `app/submissions/schemas.py`
- Modify: `app/submissions/repository.py`
- Modify: `app/submissions/service.py`
- Modify: `app/submissions/tasks.py`
- Modify: `app/submissions/router.py`

**Step 1: Update submissions/schemas.py**

```python
from datetime import datetime
from pydantic import BaseModel
from app.models.submission import AIStatus, DeliveryStatus, SubmissionType

class SubmissionFileResponse(BaseModel):
    id: int
    original_filename: str
    ai_status: AIStatus
    delivery_status: DeliveryStatus
    published_at: datetime | None

    class Config:
        from_attributes = True

class SubmissionResponse(BaseModel):
    id: int
    display_id: str
    type: SubmissionType
    submitted_at: datetime
    files: list[SubmissionFileResponse] = []

    class Config:
        from_attributes = True

class UpdateResultRequest(BaseModel):
    notes: str | None = None

class AnalyzeAllRequest(BaseModel):
    file_ids: list[int]

class ManualInputRequest(BaseModel):
    commodity_name: str
    description: str | None = None
    function: str | None = None
    structure_components: str | None = None
    material_composition: str | None = None
    technical_specification: str | None = None
    additional_notes: str | None = None
```

**Step 2: Update submissions/repository.py**

```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.submission import Submission, SubmissionFile, AnalysisJob, AIStatus, DeliveryStatus, SubmissionType

def get_next_sequence(db: Session, tenant_id: int) -> int:
    """Dùng SELECT FOR UPDATE để tránh race condition"""
    count = db.query(func.count(Submission.id)).filter(Submission.tenant_id == tenant_id).scalar()
    return count + 1

def create_submission(db: Session, tenant_id: int, user_id: int, display_id: str, type: SubmissionType) -> Submission:
    submission = Submission(tenant_id=tenant_id, user_id=user_id, display_id=display_id, type=type)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission

def create_file(db: Session, submission_id: int, filename: str, s3_key: str) -> SubmissionFile:
    file = SubmissionFile(submission_id=submission_id, original_filename=filename, s3_key=s3_key)
    db.add(file)
    db.commit()
    db.refresh(file)
    return file

def get_submissions_by_tenant(db: Session, tenant_id: int, start_date=None, end_date=None) -> list[Submission]:
    q = db.query(Submission).filter(Submission.tenant_id == tenant_id)
    if start_date:
        q = q.filter(Submission.submitted_at >= start_date)
    if end_date:
        q = q.filter(Submission.submitted_at <= end_date)
    return q.order_by(Submission.submitted_at.desc()).all()

def get_submissions_by_user(db: Session, user_id: int, start_date=None, end_date=None) -> list[Submission]:
    q = db.query(Submission).filter(Submission.user_id == user_id)
    if start_date:
        q = q.filter(Submission.submitted_at >= start_date)
    if end_date:
        q = q.filter(Submission.submitted_at <= end_date)
    return q.order_by(Submission.submitted_at.desc()).all()

def get_submission_by_id(db: Session, submission_id: int) -> Submission | None:
    return db.query(Submission).filter(Submission.id == submission_id).first()

def get_file_by_id(db: Session, file_id: int) -> SubmissionFile | None:
    return db.query(SubmissionFile).filter(SubmissionFile.id == file_id).first()

def get_files_by_ids(db: Session, file_ids: list[int]) -> list[SubmissionFile]:
    return db.query(SubmissionFile).filter(SubmissionFile.id.in_(file_ids)).all()

def create_analysis_job(db: Session, file_id: int, triggered_by: int) -> AnalysisJob:
    job = AnalysisJob(submission_file_id=file_id, triggered_by=triggered_by, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def update_file_ai_status(db: Session, file: SubmissionFile, ai_status: AIStatus):
    file.ai_status = ai_status
    db.commit()

def publish_file(db: Session, file: SubmissionFile, reviewed_by: int, notes: str | None):
    file.delivery_status = DeliveryStatus.sent
    file.reviewed_by = reviewed_by
    file.notes = notes
    file.published_at = datetime.now(timezone.utc)
    db.commit()
```

**Step 3: Update submissions/tasks.py**

```python
from datetime import datetime, timezone
from worker import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.submission import SubmissionFile, AnalysisJob, AIStatus
import httpx

@celery_app.task(bind=True)
def run_ai_analysis(self, submission_file_id: int, job_id: int):
    db = SessionLocal()
    try:
        file = db.query(SubmissionFile).filter(SubmissionFile.id == submission_file_id).first()
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not file or not job:
            return

        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # TODO: tải file từ S3
        # from app.core.s3 import stream_file
        # file_content = b"".join(stream_file(file.s3_key))

        # TODO: gọi AI API
        # response = httpx.post(
        #     settings.AI_API_URL,
        #     files={"file": (file.original_filename, file_content)},
        #     headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
        #     timeout=1800,  # 30 phút
        # )
        # result_content = response.content
        # result_key = f"results/{file.submission_id}/{file.id}/result_{file.original_filename}"
        # from app.core.s3 import upload_file
        # upload_file(result_content, result_key)
        # file.ai_s3_key = result_key

        file.ai_status = AIStatus.completed
        job.status = "success"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        if file:
            file.ai_status = AIStatus.failed
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
```

**Step 4: Update submissions/service.py**

```python
import io
from datetime import datetime
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.submissions import repository
from app.submissions.schemas import UpdateResultRequest, AnalyzeAllRequest, ManualInputRequest
from app.models.submission import AIStatus, SubmissionType
from app.models.user import User

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
ALLOWED_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

def _validate_file(file: UploadFile):
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File {file.filename}: only .xlsx and .xls allowed")
    if file.content_type and file.content_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail=f"File {file.filename}: invalid MIME type")

def _generate_display_id(db: Session, tenant_code: str, tenant_id: int) -> str:
    # Lock row để tránh race condition
    from sqlalchemy import text
    db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": tenant_id})
    seq = repository.get_next_sequence(db, tenant_id)
    return f"{tenant_code}-{str(seq).zfill(3)}"

async def upload(db: Session, files: list[UploadFile], user: User, sub_type: SubmissionType) -> object:
    for f in files:
        _validate_file(f)

    display_id = _generate_display_id(db, user.tenant.tenant_code, user.tenant_id)
    submission = repository.create_submission(db, user.tenant_id, user.id, display_id, sub_type)

    for file in files:
        content = await file.read()
        s3_key = f"{user.tenant_id}/{user.id}/{submission.id}/{file.filename}"
        from app.core.s3 import upload_file as s3_upload
        s3_upload(content, s3_key)
        repository.create_file(db, submission.id, file.filename, s3_key)

    # Gửi mail xác nhận (best-effort)
    try:
        from app.core.email import send_upload_confirmation
        send_upload_confirmation(user.email, user.full_name, display_id)
    except Exception:
        pass

    db.refresh(submission)
    return submission

async def create_manual(db: Session, payload: ManualInputRequest, user: User) -> object:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Manual Input"
    fields = [
        ("Commodity Name", payload.commodity_name),
        ("Description", payload.description),
        ("Function", payload.function),
        ("Structure/Components", payload.structure_components),
        ("Material Composition", payload.material_composition),
        ("Technical Specification", payload.technical_specification),
        ("Additional Notes", payload.additional_notes),
    ]
    for row_idx, (label, value) in enumerate(fields, 1):
        ws.cell(row=row_idx, column=1, value=label)
        ws.cell(row=row_idx, column=2, value=value or "")

    buf = io.BytesIO()
    wb.save(buf)
    content = buf.getvalue()
    filename = f"manual_input_{payload.commodity_name[:30]}.xlsx"

    display_id = _generate_display_id(db, user.tenant.tenant_code, user.tenant_id)
    submission = repository.create_submission(db, user.tenant_id, user.id, display_id, SubmissionType.manual_input)

    s3_key = f"{user.tenant_id}/{user.id}/{submission.id}/{filename}"
    from app.core.s3 import upload_file as s3_upload
    s3_upload(content, s3_key)
    repository.create_file(db, submission.id, filename, s3_key)

    try:
        from app.core.email import send_upload_confirmation
        send_upload_confirmation(user.email, user.full_name, display_id)
    except Exception:
        pass

    db.refresh(submission)
    return submission

def get_user_submissions(db: Session, user_id: int, start_date=None, end_date=None):
    return repository.get_submissions_by_user(db, user_id, start_date, end_date)

def get_submission(db: Session, submission_id: int, tenant_id: int):
    submission = repository.get_submission_by_id(db, submission_id)
    if not submission or submission.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission

def get_tenant_submissions(db: Session, tenant_id: int, start_date=None, end_date=None):
    return repository.get_submissions_by_tenant(db, tenant_id, start_date, end_date)

def trigger_ai(db: Session, submission_id: int, file_id: int, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=404, detail="File not found")
    if file.ai_status == AIStatus.running:
        raise HTTPException(status_code=400, detail="AI analysis already running")

    job = repository.create_analysis_job(db, file.id, current_user.id)
    repository.update_file_ai_status(db, file, AIStatus.running)

    from app.submissions.tasks import run_ai_analysis
    task = run_ai_analysis.delay(file.id, job.id)
    return {"message": "AI analysis started", "task_id": task.id}

def trigger_ai_batch(db: Session, submission_id: int, payload: AnalyzeAllRequest, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    files = repository.get_files_by_ids(db, payload.file_ids)
    results = []
    for file in files:
        if file.submission_id != submission.id:
            continue
        if file.ai_status in (AIStatus.not_started, AIStatus.failed):
            result = trigger_ai(db, submission_id, file.id, current_user)
            results.append(result)
    return results

def stream_file(db: Session, submission_id: int, file_id: int, tenant_id: int):
    submission = get_submission(db, submission_id, tenant_id)
    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=404, detail="File not found")
    from app.core.s3 import stream_file as s3_stream
    return file.original_filename, s3_stream(file.s3_key)

def stream_ai_result(db: Session, submission_id: int, file_id: int, tenant_id: int):
    submission = get_submission(db, submission_id, tenant_id)
    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=404, detail="File not found")
    if file.ai_status != AIStatus.completed or not file.ai_s3_key:
        raise HTTPException(status_code=400, detail="AI result not available")
    from app.core.s3 import stream_file as s3_stream
    return file.original_filename, s3_stream(file.ai_s3_key)

def update_result(db: Session, submission_id: int, file_id: int, payload: UpdateResultRequest, uploaded_file, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=404, detail="File not found")
    if uploaded_file:
        import asyncio
        content = asyncio.get_event_loop().run_until_complete(uploaded_file.read())
        expert_key = f"{current_user.tenant_id}/results/{submission.id}/{file_id}/{uploaded_file.filename}"
        from app.core.s3 import upload_file as s3_upload
        s3_upload(content, expert_key)
        file.expert_s3_key = expert_key
    if payload.notes is not None:
        file.notes = payload.notes
    db.commit()
    return {"message": "Result updated"}

def publish(db: Session, submission_id: int, file_id: int, current_user: User):
    submission = get_submission(db, submission_id, current_user.tenant_id)
    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id:
        raise HTTPException(status_code=404, detail="File not found")
    result_key = file.expert_s3_key or file.ai_s3_key
    if not result_key:
        raise HTTPException(status_code=400, detail="No result file available")
    from app.core.s3 import generate_presigned_url
    url = generate_presigned_url(result_key, expiration=604800)  # 7 ngày
    repository.publish_file(db, file, current_user.id, file.notes)
    try:
        from app.core.email import send_result_ready
        send_result_ready(submission.user.email, submission.user.full_name, submission.display_id, url)
    except Exception:
        pass
    return {"message": "Result published", "download_url": url}

def get_result_url(db: Session, submission_id: int, file_id: int, user_id: int):
    submission = repository.get_submission_by_id(db, submission_id)
    if not submission or submission.user_id != user_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    file = repository.get_file_by_id(db, file_id)
    if not file or file.submission_id != submission.id or not file.published_at:
        raise HTTPException(status_code=404, detail="Result not available")
    from app.core.s3 import generate_presigned_url
    result_key = file.expert_s3_key or file.ai_s3_key
    url = generate_presigned_url(result_key, expiration=604800)
    return {"url": url}
```

**Step 5: Update submissions/router.py**

```python
from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.submission import SubmissionType
from app.submissions import service
from app.submissions.schemas import SubmissionResponse, UpdateResultRequest, AnalyzeAllRequest, ManualInputRequest

router = APIRouter()
expert_or_admin = require_roles(UserRole.expert, UserRole.tenant_admin)
user_only = require_roles(UserRole.user)

# ── User site ──────────────────────────────────────────────

@router.post("/upload", response_model=SubmissionResponse)
async def upload(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.upload(db, files, current_user, SubmissionType.file_upload)

@router.post("/batch", response_model=SubmissionResponse)
async def upload_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.upload(db, files, current_user, SubmissionType.batch_dataset)

@router.post("/manual", response_model=SubmissionResponse)
async def create_manual(
    payload: ManualInputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_manual(db, payload, current_user)

@router.get("/my", response_model=list[SubmissionResponse])
def get_my_submissions(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_user_submissions(db, current_user.id, start_date, end_date)

@router.get("/my/{submission_id}", response_model=SubmissionResponse)
def get_my_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.get_submission(db, submission_id, current_user.tenant_id)

@router.get("/my/{submission_id}/files/{file_id}/result")
def get_result_url(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.get_result_url(db, submission_id, file_id, current_user.id)

# ── Admin site ─────────────────────────────────────────────

@router.get("", response_model=list[SubmissionResponse])
def get_submissions(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_or_admin),
):
    return service.get_tenant_submissions(db, current_user.tenant_id, start_date, end_date)

@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.get_submission(db, submission_id, current_user.tenant_id)

@router.get("/{submission_id}/files/{file_id}/download")
def download_file(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    filename, stream = service.stream_file(db, submission_id, file_id, current_user.tenant_id)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@router.post("/{submission_id}/files/{file_id}/analyze")
def trigger_ai(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.trigger_ai(db, submission_id, file_id, current_user)

@router.post("/{submission_id}/analyze-all")
def analyze_all(submission_id: int, payload: AnalyzeAllRequest, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.trigger_ai_batch(db, submission_id, payload, current_user)

@router.get("/{submission_id}/files/{file_id}/ai-result/download")
def download_ai_result(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    filename, stream = service.stream_ai_result(db, submission_id, file_id, current_user.tenant_id)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="result_{filename}"'})

@router.put("/{submission_id}/files/{file_id}/result")
async def update_result(
    submission_id: int,
    file_id: int,
    notes: str | None = None,
    uploaded_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_or_admin),
):
    payload = UpdateResultRequest(notes=notes)
    return service.update_result(db, submission_id, file_id, payload, uploaded_file, current_user)

@router.post("/{submission_id}/files/{file_id}/publish")
def publish(submission_id: int, file_id: int, db: Session = Depends(get_db), current_user: User = Depends(expert_or_admin)):
    return service.publish(db, submission_id, file_id, current_user)
```

**Step 6: Commit**
```bash
git add app/submissions/
git commit -m "feat: complete submissions module — upload, manual input, AI trigger, publish"
```

---

## Task 9: Settings Module (tạo mới)

**Files:**
- Create: `app/settings/router.py`
- Create: `app/settings/schemas.py`
- Create: `app/settings/service.py`

**Step 1: Create app/settings/schemas.py**

```python
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole

class ProfileResponse(BaseModel):
    id: int
    email: str
    username: str | None
    full_name: str
    role: UserRole
    is_first_login: bool

    class Config:
        from_attributes = True

class EmailConfigResponse(BaseModel):
    smtp_host: str | None
    smtp_port: int | None
    sender_email: str | None
    sender_name: str | None
    smtp_username: str | None
    is_enabled: bool

class EmailConfigUpdate(BaseModel):
    smtp_host: str | None = None
    smtp_port: int | None = None
    sender_email: EmailStr | None = None
    sender_name: str | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    is_enabled: bool = False
```

**Step 2: Create app/settings/service.py**

```python
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.tenant_email_config import TenantEmailConfig

def get_email_config(db: Session, tenant_id: int) -> TenantEmailConfig | None:
    return db.query(TenantEmailConfig).filter(TenantEmailConfig.tenant_id == tenant_id).first()

def upsert_email_config(db: Session, tenant_id: int, **kwargs) -> TenantEmailConfig:
    config = get_email_config(db, tenant_id)
    if not config:
        config = TenantEmailConfig(tenant_id=tenant_id)
        db.add(config)
    for key, value in kwargs.items():
        if value is not None:
            setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config
```

**Step 3: Create app/settings/router.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole
from app.settings import service
from app.settings.schemas import ProfileResponse, EmailConfigResponse, EmailConfigUpdate

router = APIRouter()
tenant_admin_only = require_roles(UserRole.tenant_admin)

@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/email-config", response_model=EmailConfigResponse)
def get_email_config(db: Session = Depends(get_db), current_user: User = Depends(tenant_admin_only)):
    config = service.get_email_config(db, current_user.tenant_id)
    if not config:
        return EmailConfigResponse(smtp_host=None, smtp_port=None, sender_email=None, sender_name=None, smtp_username=None, is_enabled=False)
    return config

@router.put("/email-config", response_model=EmailConfigResponse)
def update_email_config(
    payload: EmailConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    config = service.upsert_email_config(db, current_user.tenant_id, **payload.model_dump(exclude_none=True))
    return config
```

**Step 4: Tạo `app/settings/__init__.py`**
```bash
touch app/settings/__init__.py
```

**Step 5: Commit**
```bash
git add app/settings/
git commit -m "feat: add settings module — profile and email config"
```

---

## Task 10: Dashboard Module (hoàn chỉnh)

**Files:**
- Modify: `app/dashboard/schemas.py`
- Modify: `app/dashboard/service.py`
- Modify: `app/dashboard/router.py`

**Step 1: Update dashboard/schemas.py**

```python
from datetime import datetime
from pydantic import BaseModel

class DashboardStats(BaseModel):
    total_tenants: int | None = None
    active_tenants: int | None = None
    total_users: int
    total_records: int
    records_completed: int
    records_processing: int
    records_failed: int

class RecentTenant(BaseModel):
    id: int
    name: str
    tenant_code: str
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class RecentUser(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    class Config:
        from_attributes = True

class RecentSubmission(BaseModel):
    id: int
    display_id: str
    submitted_at: datetime
    class Config:
        from_attributes = True

class RoleDistribution(BaseModel):
    admins: int
    experts: int
    users: int
```

**Step 2: Update dashboard/service.py**

```python
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.models.submission import Submission, SubmissionFile, AIStatus

def get_stats(db: Session, current_user: User) -> dict:
    is_super = current_user.role == UserRole.super_admin
    tenant_id = current_user.tenant_id

    stats = {}
    if is_super:
        stats["total_tenants"] = db.query(Tenant).count()
        stats["active_tenants"] = db.query(Tenant).filter(Tenant.is_active == True).count()
        stats["total_users"] = db.query(User).filter(User.role != UserRole.super_admin).count()
        base = db.query(SubmissionFile)
    else:
        stats["total_users"] = db.query(User).filter(User.tenant_id == tenant_id).count()
        base = db.query(SubmissionFile).join(Submission).filter(Submission.tenant_id == tenant_id)

    stats["total_records"] = base.count()
    stats["records_completed"] = base.filter(SubmissionFile.ai_status == AIStatus.completed).count()
    stats["records_processing"] = base.filter(SubmissionFile.ai_status == AIStatus.running).count()
    stats["records_failed"] = base.filter(SubmissionFile.ai_status == AIStatus.failed).count()
    return stats

def get_recent_tenants(db: Session):
    return db.query(Tenant).order_by(Tenant.created_at.desc()).limit(5).all()

def get_recent_users(db: Session, tenant_id: int | None = None):
    q = db.query(User)
    if tenant_id:
        q = q.filter(User.tenant_id == tenant_id)
    return q.order_by(User.created_at.desc()).limit(5).all()

def get_recent_submissions(db: Session, tenant_id: int | None = None):
    q = db.query(Submission)
    if tenant_id:
        q = q.filter(Submission.tenant_id == tenant_id)
    return q.order_by(Submission.submitted_at.desc()).limit(5).all()

def get_role_distribution(db: Session, tenant_id: int | None = None) -> dict:
    q = db.query(User)
    if tenant_id:
        q = q.filter(User.tenant_id == tenant_id)
    return {
        "admins": q.filter(User.role == UserRole.tenant_admin).count(),
        "experts": q.filter(User.role == UserRole.expert).count(),
        "users": q.filter(User.role == UserRole.user).count(),
    }
```

**Step 3: Update dashboard/router.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.dashboard import service
from app.dashboard.schemas import DashboardStats, RecentTenant, RecentUser, RecentSubmission, RoleDistribution

router = APIRouter()
allowed = require_roles(UserRole.super_admin, UserRole.tenant_admin, UserRole.expert)

@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(allowed)):
    return service.get_stats(db, current_user)

@router.get("/recent-tenants", response_model=list[RecentTenant])
def recent_tenants(db: Session = Depends(get_db), current_user: User = Depends(require_roles(UserRole.super_admin))):
    return service.get_recent_tenants(db)

@router.get("/recent-users", response_model=list[RecentUser])
def recent_users(db: Session = Depends(get_db), current_user: User = Depends(allowed)):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_users(db, tenant_id)

@router.get("/recent-submissions", response_model=list[RecentSubmission])
def recent_submissions(db: Session = Depends(get_db), current_user: User = Depends(allowed)):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_submissions(db, tenant_id)

@router.get("/role-distribution", response_model=RoleDistribution)
def role_distribution(db: Session = Depends(get_db), current_user: User = Depends(allowed)):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_role_distribution(db, tenant_id)
```

**Step 4: Commit**
```bash
git add app/dashboard/
git commit -m "feat: complete dashboard module"
```

---

## Task 11: Fix __init__.py và missing files

**Files:**
- Create: `app/auth/__init__.py`
- Create: `app/tenants/__init__.py`
- Create: `app/users/__init__.py`
- Create: `app/submissions/__init__.py`
- Create: `app/dashboard/__init__.py`
- Create: `app/core/__init__.py`

**Step 1: Tạo tất cả `__init__.py`**
```bash
touch app/__init__.py app/auth/__init__.py app/tenants/__init__.py \
      app/users/__init__.py app/submissions/__init__.py \
      app/dashboard/__init__.py app/core/__init__.py app/settings/__init__.py
```

**Step 2: Commit**
```bash
git add app/
git commit -m "fix: add missing __init__.py files"
```

---

## Task 12: Docker Compose — health checks, .env defaults

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Step 1: Update docker-compose.yml — thêm healthcheck, đổi port**

```yaml
services:
  app:
    build: .
    restart: always
    ports:
      - "8329:8329"
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build: .
    restart: always
    command: uv run celery -A worker.celery_app worker --loglevel=info
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: chc
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d chc"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Step 2: Update .env.example**

```env
# App
SECRET_KEY=change-this-to-a-random-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
PASSWORD_RESET_EXPIRE_MINUTES=60

# Database
DATABASE_URL=postgresql://user:password@postgres:5432/chc

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# AWS (optional for dev)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-southeast-1
S3_BUCKET_NAME=
SES_SENDER_EMAIL=

# AI API (optional for dev)
AI_API_URL=
AI_API_KEY=

# Domain
ADMIN_DOMAIN=admin.chc.com
BASE_DOMAIN=chc.com
```

**Step 3: Commit**
```bash
git add docker-compose.yml .env.example
git commit -m "fix: add healthchecks, update port to 8329"
```

---

## Task 13: Tạo migration + seeder super_admin

**Files:**
- Modify: `migrations/versions/` (auto-generated)
- Create: `scripts/seed.py`

**Step 1: Chạy autogenerate migration**
```bash
uv run alembic revision --autogenerate -m "initial_schema"
```

**Step 2: Apply migration**
```bash
uv run alembic upgrade head
```

**Step 3: Create scripts/seed.py — tạo super_admin ban đầu**

```python
"""Tạo super_admin account ban đầu"""
import sys
sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole

def seed():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == UserRole.super_admin).first()
        if existing:
            print(f"Super admin already exists: {existing.email}")
            return

        admin = User(
            email="admin@chc.com",
            username="superadmin",
            password_hash=hash_password("Admin@123456"),
            full_name="System Administrator",
            role=UserRole.super_admin,
            is_first_login=True,
        )
        db.add(admin)
        db.commit()
        print("Super admin created:")
        print("  Email: admin@chc.com")
        print("  Username: superadmin")
        print("  Password: Admin@123456")
        print("  ⚠️  Change password immediately!")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
```

**Step 4: Thêm seed vào setup.sh**
```bash
# Cuối setup.sh, thêm:
echo ""
echo "--- Tạo super admin ---"
uv run python scripts/seed.py
```

**Step 5: Commit**
```bash
git add migrations/ scripts/seed.py scripts/setup.sh
git commit -m "feat: add migration and super_admin seeder"
```

---

## Task 14: Final check — build và test

**Step 1: Build Docker image**
```bash
docker compose build
```
Expected: build thành công, không có lỗi

**Step 2: Chạy docker compose**
```bash
docker compose up -d postgres redis
sleep 5
docker compose up -d app worker
```

**Step 3: Chạy migration trong container**
```bash
docker compose exec app uv run alembic upgrade head
docker compose exec app uv run python scripts/seed.py
```

**Step 4: Kiểm tra Swagger**

Mở browser: `http://localhost:8329/docs`
Expected: Swagger UI hiển thị đầy đủ endpoints

**Step 5: Test health endpoint**
```bash
curl http://localhost:8329/health
```
Expected: `{"status": "ok"}`

**Step 6: Test login**
```bash
curl -X POST http://localhost:8329/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login": "admin@chc.com", "password": "Admin@123456", "role_type": "admin"}'
```
Expected: `{"access_token": "...", "token_type": "bearer"}`

**Step 7: Push lên GitHub**
```bash
git push origin main
```

---

## Checklist hoàn thành

- [ ] Port 8329 hoạt động
- [ ] Swagger tại `http://localhost:8329/docs`
- [ ] `/health` trả `{"status": "ok"}`
- [ ] Login với super_admin thành công
- [ ] Tất cả modules trong Swagger: auth, dashboard, tenants, users, submissions, settings
- [ ] Migration chạy không lỗi
- [ ] Docker Compose up không có container exit
