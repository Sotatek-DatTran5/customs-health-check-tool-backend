#!/bin/bash

echo "=== CHC Backend Status ==="
echo ""

docker compose ps

echo ""
echo "--- Logs gần nhất (app) ---"
docker compose logs app --tail=20

echo ""
echo "--- Logs gần nhất (worker) ---"
docker compose logs worker --tail=10

echo ""
echo "--- LocalStack health ---"
curl -s "http://localhost:4566/_localstack/health" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'S3: {d.get(\"s3\",{}).get(\"status\",\"N/A\")}')" || echo "LocalStack unreachable"
