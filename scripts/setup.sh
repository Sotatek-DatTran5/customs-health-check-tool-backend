#!/bin/bash
set -e

echo "=== CHC Backend Setup ==="

# 1. Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] Created .env from .env.example"
else
    echo "[SKIP] .env already exists"
fi

# 2. Install dependencies
echo ""
echo "--- Installing dependencies ---"
uv sync

# 3. Start infrastructure services
echo ""
echo "--- Starting postgres, redis, localstack, mailhog ---"
docker compose up -d postgres redis localstack mailhog

# 4. Wait for postgres
echo "--- Waiting for postgres..."
for i in $(seq 1 30); do
    if docker compose exec postgres pg_isready -U user -d chc > /dev/null 2>&1; then
        echo "Postgres is ready"
        break
    fi
    echo "  ... waiting ($i/30)"
    sleep 2
done

# 5. Run migrations (create tables)
echo ""
echo "--- Running database migrations ---"
uv run alembic upgrade head 2>/dev/null || echo "[INFO] No migrations found, using create_all fallback"

# 6. Seed super admin
echo ""
echo "--- Seeding super admin ---"
uv run python scripts/seed.py

# 7. Init LocalStack S3 bucket
echo ""
echo "--- Init LocalStack S3 bucket ---"
./scripts/setup-local.sh

echo ""
echo "=== Setup complete ==="
echo ""
echo "Start the app:  ./scripts/start.sh"
echo "API docs:       http://localhost:8329/docs"
echo "MailHog UI:     http://localhost:8025"
echo ""
echo "Super Admin:    admin@chc.com / Admin@123"
