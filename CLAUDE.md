# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

**CHC Backend** — E-Tariff Classification & Custom Health Check Platform (Python / FastAPI)

- **Tech Stack**: Python 3.11+ / FastAPI, PostgreSQL, Celery + Redis, AWS S3, SMTP email, JWT + Redis blacklist
- **Multi-tenant**: Wildcard DNS (*.chc.com), subdomain-based tenant isolation
- **Actors**: super_admin, tenant_admin, expert, user
- **Modules**: CHC (5 modules), E-Tariff (Manual + Batch), Admin Portal (dashboard, tenants, users, experts, requests, settings)
- **BRD**: `BRD_E-Tariff_CHC_v2.docx.pdf` (business requirements, acceptance criteria)
- **Spec file**: `miêu tả dự án.txt` (detailed business logic in Vietnamese)
- **Git root**: `./`

## Architecture

```
app/
├── core/           # Config, DB, security, middleware, email, storage
├── models/         # SQLAlchemy models (tenant, user, request, request_file)
├── auth/           # Login, logout, refresh token, password reset/change
├── requests/       # CHC orders, E-Tariff, assign, approve, cancel
├── users/          # User CRUD, onboarding, locale
├── tenants/        # Tenant CRUD, branding, expert management
├── dashboard/      # Stats, recent activity
└── settings/       # Profile, email config
```

## Key Business Flows

- **Request lifecycle**: Pending → Processing → Completed → Delivered → Cancelled
- **CHC modules**: item_code_generator, tariff_classification, customs_valuation, non_tariff_measures, exim_statistics
- **E-Tariff**: Manual mode (form input) + Batch mode (Excel upload), daily limit per tenant

## Commands

```bash
# Setup
./scripts/setup.sh          # Install deps, start docker, migrate, seed

# Run
./scripts/start.sh          # Start all services
./scripts/stop.sh           # Stop all services
./scripts/status.sh         # Check service status

# Dev (without Docker for app)
uv run uvicorn app.main:app --reload --port 8329
uv run celery -A worker.celery_app worker --loglevel=info

# Migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Seed
uv run python scripts/seed.py
```

## Workflows

- Primary workflow: `./.claude/rules/primary-workflow.md`
- Development rules: `./.claude/rules/development-rules.md`
- Orchestration protocols: `./.claude/rules/orchestration-protocol.md`
- Documentation management: `./.claude/rules/documentation-management.md`

**IMPORTANT:** Before you plan or proceed any implementation, always read `./miêu tả dự án.txt` to get project context.
**IMPORTANT:** Follow the development rules in `./.claude/rules/development-rules.md`.

## Hook Response Protocol

### Privacy Block Hook (`@@PRIVACY_PROMPT@@`)

When a tool call is blocked by the privacy-block hook, the output contains a JSON marker between `@@PRIVACY_PROMPT_START@@` and `@@PRIVACY_PROMPT_END@@`. **You MUST use the `AskUserQuestion` tool** to get proper user approval.

## Python Scripts (Skills)

When running Python scripts from `.claude/skills/`, use the venv Python interpreter:
- **Linux/macOS:** `.claude/skills/.venv/bin/python3 scripts/xxx.py`

## Code Standards

- Keep files under 200 lines; modularize if exceeded
- Use kebab-case file names (descriptive for LLM tools)
- Follow patterns in `./docs/code-standards.md`
- Docs kept in `./docs/` — update after significant changes
