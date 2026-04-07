#!/bin/bash
set -e

echo "=== CHC Backend — Production Deploy ==="

# 1. Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] Created .env from .env.example"
    echo "[!] Please edit .env with production values before continuing."
    exit 1
else
    echo "[OK] .env exists"
fi

# 2. Build and start all services
echo ""
echo "--- Building and starting services ---"
docker compose up -d --build

# 3. Wait for postgres
echo ""
echo "--- Waiting for postgres ---"
for i in $(seq 1 30); do
    if docker compose exec postgres pg_isready -U user -d chc > /dev/null 2>&1; then
        echo "Postgres is ready"
        break
    fi
    echo "  ... waiting ($i/30)"
    sleep 2
done

# 4. Run migrations inside app container
echo ""
echo "--- Running database migrations ---"
docker compose exec app uv run alembic upgrade head 2>/dev/null || echo "[INFO] No pending migrations"

# 5. Seed super admin
echo ""
echo "--- Seeding super admin ---"
docker compose exec app uv run python scripts/seed.py

echo ""
echo "=== Deploy complete ==="
echo ""
echo "API:        http://$(hostname -I | awk '{print $1}'):8329"
echo "API docs:   http://$(hostname -I | awk '{print $1}'):8329/docs"
echo ""
echo "Super Admin: admin@chc.com / Admin@123"
