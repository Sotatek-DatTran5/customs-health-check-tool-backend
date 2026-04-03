# Missing Backend Features — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all missing backend features identified from design review: Manual Input, Settings endpoints, Dashboard recent + role distribution, CHC list filters.

**Architecture:** Add new endpoints + schemas following existing patterns (router/service/repository/schemas per module). No new models needed — reusing existing ones.

**Tech Stack:** Python / FastAPI / SQLAlchemy / Pydantic

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Manual Input endpoint (`POST /submissions/manual`) | `submissions/router.py`, `submissions/service.py`, `submissions/schemas.py` |
| 2 | Settings — Profile view (`GET /settings/profile`) | New `settings/` module |
| 3 | Settings — Email config CRUD (`GET+PUT /settings/email-config`) | New `settings/` module + model |
| 4 | Dashboard — Recent endpoints (tenants/users/submissions) | `dashboard/router.py`, `dashboard/service.py`, `dashboard/schemas.py` |
| 5 | Dashboard — Role distribution (`GET /dashboard/role-distribution`) | `dashboard/router.py`, `dashboard/service.py`, `dashboard/schemas.py` |
| 6 | Submissions — List filter query params | `submissions/router.py`, `submissions/service.py`, `submissions/schemas.py` |
| 7 | Register `settings` router in `main.py` | `main.py` |

---

## Task 1: Manual Input Endpoint

### `POST /submissions/manual`

**Goal:** User submits structured form → system generates Excel file → saved to S3 → submission created.

**Files:**
- Modify: `app/submissions/schemas.py`
- Modify: `app/submissions/router.py`
- Modify: `app/submissions/service.py`
- Modify: `app/main.py`

**Step 1: Add schemas for manual input**

Add to `app/submissions/schemas.py`:

```python
class ManualInputRequest(BaseModel):
    commodity_name: str
    description: str
    function: str
    structure_components: str
    material_composition: str
    technical_specification: str
    additional_notes: str | None = None
```

**Step 2: Add service method**

Add to `app/submissions/service.py`:

```python
def create_manual_submission(db: Session, data: ManualInputRequest, user: User) -> SubmissionResponse:
    # 1. Create submission record (type=manual_input)
    # 2. Generate Excel from form data (stub: save raw data JSON for now)
    # 3. Save to S3 (stub: skip for now)
    # 4. Create submission_file record
    # 5. Return SubmissionResponse
    # NOTE: S3 and Excel generation are stubs — implement in Phase 2
```

**Step 3: Add router endpoint**

Add to `app/submissions/router.py` under `# ── User site ──`:

```python
@router.post("/manual", response_model=SubmissionResponse)
def create_manual_submission(
    payload: ManualInputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_manual_submission(db, payload, current_user)
```

**Step 4: Commit**

```bash
git add app/submissions/router.py app/submissions/service.py app/submissions/schemas.py app/main.py
git commit -m "feat: add POST /submissions/manual endpoint"
```

---

## Task 2: Settings — Profile Endpoint

### `GET /settings/profile`

**Goal:** Current user views their own account info (read-only).

**Files:**
- Create: `app/settings/router.py`
- Create: `app/settings/schemas.py`
- Modify: `app/main.py`

**Step 1: Create schemas**

Create `app/settings/schemas.py`:

```python
from pydantic import BaseModel

class ProfileResponse(BaseModel):
    full_name: str
    email: str
    role: str
    username: str

    class Config:
        from_attributes = True
```

**Step 2: Create router**

Create `app/settings/router.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.settings.schemas import ProfileResponse

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return ProfileResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role.value,
        username=current_user.username,
    )
```

**Step 3: Register router**

Modify `app/main.py` — add import and include_router:

```python
from app.settings.router import router as settings_router
# ...
app.include_router(settings_router)
```

**Step 4: Commit**

```bash
git add app/settings/ app/main.py
git commit -m "feat: add GET /settings/profile endpoint"
```

---

## Task 3: Settings — Email Config

### `GET /settings/email-config` + `PUT /settings/email-config`

**Goal:** Tenant admin views and updates per-tenant SMTP configuration.

**Files:**
- Create: `app/settings/router.py` (append)
- Create: `app/settings/service.py`
- Create: `app/settings/schemas.py` (append)
- Modify: `app/main.py`

**Step 1: Check if model exists**

```bash
grep -r "tenant_email_config" /Users/dat_macbook/Documents/2025/SOTATEK/dự\ án\ check\ thuế/chc-backend/app/models/
```

**Step 2: If no model, create**

If `TenantEmailConfig` model doesn't exist in `app/models/`, create `app/models/tenant_email_config.py`:

```python
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class TenantEmailConfig(Base):
    __tablename__ = "tenant_email_configs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False)
    smtp_host = Column(String, nullable=False)
    smtp_port = Column(Integer, nullable=False)
    sender_email = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    smtp_username = Column(String, nullable=False)
    smtp_password = Column(String, nullable=False)  # encrypt in production
    is_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Step 3: Append to schemas**

Append to `app/settings/schemas.py`:

```python
class EmailConfigResponse(BaseModel):
    smtp_host: str
    smtp_port: int
    sender_email: str
    sender_name: str
    smtp_username: str
    smtp_password: str  # return masked or omit in real implementation
    is_enabled: bool

    class Config:
        from_attributes = True


class EmailConfigUpdate(BaseModel):
    smtp_host: str
    smtp_port: int
    sender_email: str
    sender_name: str
    smtp_username: str
    smtp_password: str
    is_enabled: bool = False
```

**Step 4: Create service**

Create `app/settings/service.py`:

```python
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.tenant_email_config import TenantEmailConfig


def get_email_config(db: Session, tenant_id: int) -> TenantEmailConfig | None:
    return db.query(TenantEmailConfig).filter(TenantEmailConfig.tenant_id == tenant_id).first()


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
```

**Step 5: Add router endpoints**

Append to `app/settings/router.py`:

```python
from app.core.dependencies import require_roles
from app.models.user import UserRole
from app.settings.service import get_email_config, upsert_email_config
from app.settings.schemas import EmailConfigResponse, EmailConfigUpdate

tenant_admin_only = require_roles(UserRole.tenant_admin)


@router.get("/email-config", response_model=EmailConfigResponse | None)
def get_email_config_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    return get_email_config(db, current_user.tenant_id)


@router.put("/email-config", response_model=EmailConfigResponse)
def update_email_config_handler(
    payload: EmailConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(tenant_admin_only),
):
    config = upsert_email_config(db, current_user.tenant_id, payload.model_dump())
    return config
```

**Step 6: Commit**

```bash
git add app/settings/ app/models/ app/main.py
git commit -m "feat: add /settings/email-config GET and PUT endpoints"
```

---

## Task 4: Dashboard — Recent Endpoints

### `GET /dashboard/recent-tenants`, `GET /dashboard/recent-users`, `GET /dashboard/recent-submissions`

**Goal:** Dashboard recent lists, scoped by role.

**Files:**
- Modify: `app/dashboard/schemas.py`
- Modify: `app/dashboard/router.py`
- Modify: `app/dashboard/service.py`

**Step 1: Add schemas**

Append to `app/dashboard/schemas.py`:

```python
class RecentTenant(BaseModel):
    id: int
    name: str
    tenant_code: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecentUser(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecentSubmission(BaseModel):
    id: int
    display_id: str
    type: str
    submitted_at: datetime
    uploaded_by: str  # full_name of user

    class Config:
        from_attributes = True
```

**Step 2: Add service methods**

Append to `app/dashboard/service.py`:

```python
def get_recent_tenants(db: Session, limit: int = 10) -> list[Tenant]:
    return db.query(Tenant).order_by(Tenant.created_at.desc()).limit(limit).all()


def get_recent_users(db: Session, tenant_id: int | None, role: UserRole | None, limit: int = 10) -> list[User]:
    query = db.query(User)
    if tenant_id:
        query = query.filter(User.tenant_id == tenant_id)
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.created_at.desc()).limit(limit).all()


def get_recent_submissions(db: Session, tenant_id: int | None, limit: int = 10) -> list[dict]:
    query = db.query(Submission).join(User)
    if tenant_id:
        query = query.filter(Submission.tenant_id == tenant_id)
    results = query.order_by(Submission.submitted_at.desc()).limit(limit).all()
    return [
        {
            "id": s.id,
            "display_id": s.display_id,
            "type": s.type.value,
            "submitted_at": s.submitted_at,
            "uploaded_by": s.user.full_name,
        }
        for s in results
    ]
```

**Step 3: Add router endpoints**

Append to `app/dashboard/router.py`:

```python
@router.get("/recent-tenants", response_model=list[RecentTenant])
def get_recent_tenants(
    db: Session = Depends(get_db),
    _=Depends(super_admin_only),
    limit: int = Query(default=10, ge=1, le=50),
):
    return service.get_recent_tenants(db, limit)


@router.get("/recent-users", response_model=list[RecentUser])
def get_recent_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(allowed_roles),
    limit: int = Query(default=10, ge=1, le=50),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_users(db, tenant_id, limit=limit)


@router.get("/recent-submissions", response_model=list[RecentSubmission])
def get_recent_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(allowed_roles),
    limit: int = Query(default=10, ge=1, le=50),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    return service.get_recent_submissions(db, tenant_id, limit)
```

**Step 4: Commit**

```bash
git add app/dashboard/
git commit -m "feat: add dashboard recent endpoints (tenants, users, submissions)"
```

---

## Task 5: Dashboard — Role Distribution

### `GET /dashboard/role-distribution`

**Goal:** Count users by role for dashboard chart.

**Files:**
- Modify: `app/dashboard/schemas.py`
- Modify: `app/dashboard/router.py`
- Modify: `app/dashboard/service.py`

**Step 1: Add schema**

Append to `app/dashboard/schemas.py`:

```python
class RoleDistribution(BaseModel):
    super_admin: int
    tenant_admin: int
    expert: int
    user: int
```

**Step 2: Add service method**

Append to `app/dashboard/service.py`:

```python
from sqlalchemy import func

def get_role_distribution(db: Session, tenant_id: int | None = None) -> dict:
    query = db.query(User.role, func.count(User.id)).group_by(User.role)

    if tenant_id:
        query = query.filter(User.tenant_id == tenant_id)

    counts = {role.value: 0 for role in UserRole}
    for role, count in query.all():
        counts[role.value] = count
    return counts
```

**Step 3: Add router endpoint**

Append to `app/dashboard/router.py`:

```python
@router.get("/role-distribution", response_model=RoleDistribution)
def get_role_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(allowed_roles),
):
    tenant_id = None if current_user.role == UserRole.super_admin else current_user.tenant_id
    counts = service.get_role_distribution(db, tenant_id)
    return RoleDistribution(**counts)
```

**Step 4: Commit**

```bash
git add app/dashboard/
git commit -m "feat: add GET /dashboard/role-distribution endpoint"
```

---

## Task 6: Submissions — List Filters

### `GET /submissions` with query params

**Goal:** Admin list submissions with filters: date range, processing status, AI status, delivery status, search by file name/tenant.

**Files:**
- Modify: `app/submissions/schemas.py`
- Modify: `app/submissions/router.py`
- Modify: `app/submissions/service.py`

**Step 1: Add filter schema**

Append to `app/submissions/schemas.py`:

```python
from app.models.submission import SubmissionType

class SubmissionFilter(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    processing_status: str | None = None  # aggregate: all/pending/processing/completed/failed
    ai_status: AIStatus | None = None
    delivery_status: DeliveryStatus | None = None
    search: str | None = None
    type: SubmissionType | None = None
```

**Step 2: Add service method**

Append to `app/submissions/service.py`:

```python
def get_tenant_submissions_filtered(
    db: Session,
    tenant_id: int,
    date_from: datetime | None,
    date_to: datetime | None,
    ai_status: AIStatus | None,
    delivery_status: DeliveryStatus | None,
    search: str | None,
    type: SubmissionType | None,
) -> list[Submission]:
    query = db.query(Submission).filter(Submission.tenant_id == tenant_id)

    if date_from:
        query = query.filter(Submission.submitted_at >= date_from)
    if date_to:
        query = query.filter(Submission.submitted_at <= date_to)
    if search:
        # search in display_id or file names
        query = query.join(SubmissionFile).filter(
            or_(
                Submission.display_id.ilike(f"%{search}%"),
                SubmissionFile.original_filename.ilike(f"%{search}%"),
            )
        )
    if type:
        query = query.filter(Submission.type == type)
    if ai_status or delivery_status:
        # Aggregate: if ai_status filter, include submissions that have at least one file with that status
        query = query.join(SubmissionFile)
        if ai_status:
            query = query.filter(SubmissionFile.ai_status == ai_status)
        if delivery_status:
            query = query.filter(SubmissionFile.delivery_status == delivery_status)

    return query.distinct().all()
```

**Step 3: Update router**

Modify `app/submissions/router.py` — update `get_submissions`:

```python
from datetime import datetime
from app.models.submission import AIStatus, DeliveryStatus, SubmissionType

@router.get("", response_model=list[SubmissionResponse])
def get_submissions(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    ai_status: AIStatus | None = None,
    delivery_status: DeliveryStatus | None = None,
    search: str | None = None,
    type: SubmissionType | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(expert_or_admin),
):
    return service.get_tenant_submissions_filtered(
        db, current_user.tenant_id,
        date_from, date_to, ai_status, delivery_status, search, type
    )
```

**Step 4: Commit**

```bash
git add app/submissions/
git commit -m "feat: add query filters to GET /submissions endpoint"
```

---

## Task 7: Final Verification

**Step 1: Run syntax check**

```bash
cd /Users/dat_macbook/Documents/2025/SOTATEK/dự\ án\ check\ thuế/chc-backend
python -c "from app.main import app; print('OK')"
```

**Step 2: Check routes registered**

```bash
grep -r "include_router" app/main.py
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: implement missing backend features (Manual Input, Settings, Dashboard, Filters)"
```

---

## Plan complete. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
