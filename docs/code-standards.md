# CHC Backend — Code Standards

> Created: 2026-04-02

---

## 1. Python Style

- **Python 3.11+** — use modern syntax (`|` union types, `|` for `None` unions)
- **Type hints** on all function signatures; use `from __future__ import annotations` where needed
- **Docstrings** for all public classes and non-trivial functions
- **Line length** — follow Black default (88 chars)
- **Import order**: stdlib → third-party → local (enforced by isort)

---

## 2. Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Python files | kebab-case | `submission_service.py` |
| Classes | PascalCase | `SubmissionService` |
| Functions / variables | snake_case | `get_user_submissions` |
| Constants | SCREAMING_SNAKE | `CELERY_BROKER_URL` |
| SQL tables | snake_case (plural) | `submission_files` |
| Enum values | snake_case | `tenant_admin` |
| Env vars | SCREAMING_SNAKE | `DATABASE_URL` |

**File naming principle:** Use long, descriptive names if they make the purpose clear. LLMs navigating the codebase via Grep/Glob should be able to understand a file's purpose from its name alone.

---

## 3. Project Structure

```
app/
├── main.py                  # FastAPI app entry, include all routers, minimal logic
├── core/                    # Shared infrastructure only (no business logic)
│   ├── config.py
│   ├── database.py
│   ├── redis.py
│   ├── security.py
│   ├── middleware.py
│   └── dependencies.py
├── models/                  # SQLAlchemy models only
├── auth/                    # One module per feature area
│   ├── router.py            # FastAPI routes + tags
│   ├── service.py           # Business logic (no FastAPI deps)
│   ├── repository.py        # DB queries (optional, for complex queries)
│   └── schemas.py          # Pydantic request/response models
├── tenants/
├── users/
├── submissions/
└── dashboard/
```

**Rules:**
- Router files should have **zero business logic** — only HTTP handling and dependency injection
- Service files contain **all business logic**
- Repository files contain **SQLAlchemy queries only**
- Never put business logic in `main.py`
- Schemas in `schemas.py`, not inline in router

---

## 4. FastAPI Patterns

### Route definitions
```python
router = APIRouter(tags=["resource"])

@router.get("", response_model=list[ItemResponse])
def list_items(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ...

@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ...
```

### HTTP status codes
- `200 OK` — default for GET, PUT
- `201 Created` — POST creating a resource
- `204 No Content` — DELETE (return nothing)
- `400 Bad Request` — validation errors raised by FastAPI
- `401 Unauthorized` — invalid/missing/revoked token
- `403 Forbidden` — insufficient role
- `404 Not Found` — resource not found or wrong tenant

### Error handling
- Use `HTTPException` for expected errors
- Wrap in `try/except` only for truly unexpected errors
- Never swallow exceptions silently

### Dependencies
- Auth deps in `dependencies.py`: `get_current_user`, `require_roles(*roles)`
- DB session via `Depends(get_db)` — always in a `finally: db.close()` pattern (handled by FastAPI)

---

## 5. SQLAlchemy Patterns

### Model definition (SQLAlchemy 2.0)
```python
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class MyModel(Base):
    __tablename__ = "my_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
```

### Query pattern
```python
def get_by_id(db: Session, id: int) -> MyModel | None:
    return db.query(MyModel).filter(MyModel.id == id).first()

def get_by_tenant(db: Session, tenant_id: int) -> list[MyModel]:
    return db.query(MyModel).filter(MyModel.tenant_id == tenant_id).all()
```

### Always commit explicitly
```python
db.add(instance)
db.commit()
db.refresh(instance)  # get DB-generated fields
return instance
```

---

## 6. Pydantic Schemas

- Use `BaseModel` for request/response
- Use `ConfigDict` for orm_mode / from_attributes
- Separate **Create**, **Update**, **Response** schemas
- Use `datetime` with `timezone=True`
- Response models should match what the client needs — not the DB model directly

```python
class ItemCreate(BaseModel):
    name: str
    description: str | None = None

class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
```

---

## 7. Security Rules

- **Never** log or expose passwords, tokens, or API keys
- **Never** commit `.env`, `credentials.json`, or any file with real secrets
- Use `bcrypt` for password hashing (via `passlib` or direct `bcrypt`)
- Always validate `tenant_id` scope in services (even if middleware already sets it)
- Token blacklist on logout with correct TTL
- Presigned S3 URLs for user downloads — never expose raw S3 keys

---

## 8. Git Conventions

### Commit message format
```
<type>: <short summary>

[optional body]
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

**Examples:**
```
feat: add tenant subdomain middleware
fix: correct tenant_id scope in submission queries
docs: add API authentication section
refactor: split submissions service into router/service
test: add coverage for auth token blacklist
chore: update .env.example
```

### Branch naming
- `feature/<short-description>`
- `fix/<short-description>`
- `docs/<short-description>`

### Pre-commit checks
- Run linter before commit
- Run tests before push
- Never push secrets or credentials to the repository

---

## 9. File Size Management

- **Target: < 200 lines per file**
- If a file exceeds 200 lines, consider splitting by:
  - Extract utility functions to a shared module
  - Split a large service into multiple focused services
  - Separate router endpoints into separate route files
- Pydantic schemas, constants, and helpers are exceptions — keep them grouped by domain

---

## 10. Testing Rules

- **No mocks for trivial things** — test real behavior when possible
- **No fake data that passes tests** — use realistic test fixtures
- **Test error paths** — 401, 403, 404 cases
- **Do not skip failing tests** to pass CI
- High coverage target for business logic in services

---

## 11. TODO Markers

Stub implementations MUST be marked with `TODO:` comments indicating what remains:

```python
# TODO: implement S3 upload
# TODO: integrate AI API (7–15 min processing)
# TODO: send email via Celery task
```

These are tracked in `docs/README.md` under **TODO / Incomplete Areas** and the project roadmap.
