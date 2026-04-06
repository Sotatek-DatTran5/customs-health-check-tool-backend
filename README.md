# CHC Backend

**E-Tariff Classification & Custom Health Check Platform** — A multi-tenant backend built with FastAPI for customs compliance services.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Python 3.11+ / FastAPI |
| ORM | SQLAlchemy 2.0 (declarative mapped columns) |
| Database | PostgreSQL 16 |
| Task Queue | Celery + Redis |
| Cache / Auth | Redis (JWT blacklist, rate limiting) |
| File Storage | AWS S3 (LocalStack for dev) |
| Email | SMTP (MailHog for dev, AWS SES for prod) |
| Auth | JWT access + refresh tokens, bcrypt |
| Package Manager | uv |
| Containerization | Docker Compose |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) package manager

### Setup & Run

```bash
git clone git@github.com:sotatek-dev/consulting-chc-be.git
cd consulting-chc-be

# One-command setup: install deps, start infra, migrate, seed
./scripts/setup.sh

# Start app + worker
./scripts/start.sh
```

After setup:

| Service | URL |
|---|---|
| API Docs (Swagger) | http://localhost:8329/docs |
| API Docs (ReDoc) | http://localhost:8329/redoc |
| MailHog (email viewer) | http://localhost:8025 |
| LocalStack S3 | http://localhost:4566 |

**Default Super Admin:** `admin@chc.com` / `Admin@123`

### Manual Dev (without Docker for app)

```bash
# Start infrastructure only
docker compose up -d postgres redis localstack mailhog

# Run app
uv run uvicorn app.main:app --reload --port 8329

# Run worker (separate terminal)
uv run celery -A worker.celery_app worker --loglevel=info
```

---

## Project Structure

```
chc-backend/
├── app/
│   ├── main.py                    # FastAPI entry, middleware, router registration
│   ├── core/
│   │   ├── config.py              # Settings from .env
│   │   ├── database.py            # SQLAlchemy engine + session
│   │   ├── security.py            # JWT, bcrypt, password policy
│   │   ├── middleware.py          # Multi-tenant subdomain routing
│   │   ├── dependencies.py       # Auth guards (get_current_user, require_roles)
│   │   ├── storage.py            # S3 upload/download/presigned URLs
│   │   ├── email.py              # SMTP sender
│   │   ├── email_service.py      # 8 email templates x 4 languages
│   │   └── redis.py              # Redis client
│   ├── models/
│   │   ├── tenant.py             # Tenant + branding config
│   │   ├── user.py               # User + company profile + locale
│   │   ├── request.py            # Request + RequestFile + status flow
│   │   ├── tenant_email_config.py
│   │   └── password_reset_token.py
│   ├── auth/                     # Login, logout, refresh, password reset/change
│   ├── requests/                 # CHC orders, E-Tariff, assign, approve, cancel
│   ├── users/                    # User CRUD, onboarding, locale
│   ├── tenants/                  # Tenant CRUD, branding, expert management
│   ├── dashboard/                # Stats, recent activity, role distribution
│   └── settings/                 # Profile, email config
├── migrations/                   # Alembic migrations
├── scripts/                      # Setup, start, stop, seed, status
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── worker.py                     # Celery app entry
└── alembic.ini
```

---

## API Endpoints

### Auth (`/auth`)

| Method | Path | Description | Access |
|---|---|---|---|
| POST | `/auth/login` | Login (returns access + refresh token) | Public |
| POST | `/auth/refresh` | Refresh access token | Public |
| POST | `/auth/logout` | Logout (blacklist token) | Authenticated |
| POST | `/auth/change-password` | Change password | Authenticated |
| POST | `/auth/reset-password` | Reset password via token | Public |

### Requests (`/requests`)

**User Portal:**

| Method | Path | Description |
|---|---|---|
| POST | `/requests/chc` | Create CHC order (upload ECUS + pick modules) |
| POST | `/requests/etariff/manual` | E-Tariff manual classification |
| POST | `/requests/etariff/batch` | E-Tariff batch (Excel upload) |
| GET | `/requests/my` | List my requests |
| GET | `/requests/my/{id}` | Request detail |
| POST | `/requests/my/{id}/cancel` | Cancel request |
| GET | `/requests/my/{id}/files/{fid}/result` | Download result |

**Admin Portal:**

| Method | Path | Description |
|---|---|---|
| GET | `/requests` | List all requests (filter by status/type/search) |
| GET | `/requests/{id}` | Request detail |
| POST | `/requests/{id}/assign` | Assign expert → status: Processing |
| POST | `/requests/{id}/files/{fid}/upload-result` | Expert uploads result (Excel+PDF) |
| POST | `/requests/{id}/approve` | Admin approves → status: Delivered |
| GET | `/requests/{id}/files/{fid}/download` | Download uploaded file |

### Users (`/users`)

| Method | Path | Description | Access |
|---|---|---|---|
| GET | `/users` | List tenant users | Admin |
| POST | `/users` | Create user (auto-gen password, send email) | Admin |
| PUT | `/users/{id}` | Update user | Admin |
| DELETE | `/users/{id}` | Soft delete user | Admin |
| POST | `/users/{id}/reset-password` | Send reset email | Admin |
| POST | `/users/onboarding` | Complete company profile (first login) | User |
| PUT | `/users/locale` | Change display language | User |

### Tenants (`/tenants`)

| Method | Path | Description | Access |
|---|---|---|---|
| GET | `/tenants` | List all tenants | Super Admin |
| POST | `/tenants` | Create tenant + admin account | Super Admin |
| PUT | `/tenants/{id}` | Update tenant (branding, limits) | Super Admin |
| DELETE | `/tenants/{id}` | Soft delete tenant | Super Admin |
| POST | `/tenants/{id}/logo` | Upload tenant logo | Super Admin |
| GET | `/tenants/experts/all` | List all experts | Admin+ |
| POST | `/tenants/experts` | Create expert (cross-tenant) | Admin+ |

### Dashboard (`/dashboard`)

| Method | Path | Description |
|---|---|---|
| GET | `/dashboard/stats` | Request counts by status, period stats |
| GET | `/dashboard/recent-tenants` | Recent tenants (Super Admin) |
| GET | `/dashboard/recent-users` | Recent users |
| GET | `/dashboard/recent-requests` | Recent requests |
| GET | `/dashboard/role-distribution` | User count by role |

### Settings (`/settings`)

| Method | Path | Description |
|---|---|---|
| GET | `/settings/profile` | Get profile + company info |
| PUT | `/settings/profile` | Update profile |
| GET | `/settings/email-config` | Get tenant SMTP config |
| PUT | `/settings/email-config` | Update tenant SMTP config |

---

## Business Logic

### Request Status Flow

```
User creates → [Pending]
Admin assigns expert → [Processing]
Expert uploads result → [Completed]
Admin approves → [Delivered] → email with download links to User
User cancels → [Cancelled] (from any status except Delivered/Cancelled)
```

### Roles & Permissions

| Role | Scope | Key Permissions |
|---|---|---|
| Super Admin | Cross-tenant | Manage tenants, admins, view all data |
| Admin | Per-tenant | Manage users/experts, assign/approve requests |
| Expert | Cross-tenant | Process assigned requests, upload results |
| User | Per-tenant | Create requests, view own data, download results |

### CHC Modules

Users can select one or more modules per CHC request:

- **Item Code Generator** — Generate NPL/SP codes for missing items
- **Tariff Classification Testing** — Verify HS code accuracy
- **Customs Valuation Testing** — Review customs value calculations
- **Non-tariff Measures Testing** — Check permits, licenses, compliance
- **Exim Statistics** — Import/export trade overview

### Security

- JWT access token (24h) + refresh token (7d)
- bcrypt password hashing
- Password policy: 8+ chars, uppercase + lowercase + digit
- Brute-force protection: lock after 5 failed attempts (15 min)
- Multi-tenant data isolation via `tenant_id` on all queries
- CORS restricted to valid domains
- File upload validation: .xlsx/.xls only, max 50MB
- S3 presigned URLs for secure file delivery

### i18n

Email templates support 4 languages: Vietnamese (default), English, Korean, Chinese. User locale stored in profile.

---

## Environment Variables

See [`.env.example`](.env.example) for full list. Key variables:

| Variable | Description | Dev Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:password@localhost:5432/chc` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key | (change in production!) |
| `AWS_ENDPOINT_URL` | S3 endpoint (LocalStack) | `http://localhost:4566` |
| `SMTP_HOST` | SMTP server | `localhost` (MailHog) |
| `ADMIN_DOMAIN` | Admin portal domain | `localhost` |
| `BASE_DOMAIN` | Base domain for subdomains | `localhost` |

---

## Database Migrations

```bash
# Apply migrations
uv run alembic upgrade head

# Create new migration after model changes
uv run alembic revision --autogenerate -m "description"

# Rollback
uv run alembic downgrade -1
```

---

## Scripts

| Script | Description |
|---|---|
| `scripts/setup.sh` | Full setup: deps, docker, migrate, seed |
| `scripts/start.sh` | Start all services via Docker Compose |
| `scripts/stop.sh` | Stop all services |
| `scripts/status.sh` | Check service health |
| `scripts/setup-local.sh` | Init LocalStack S3 bucket |
| `scripts/seed.py` | Create super admin account |
