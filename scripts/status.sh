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
