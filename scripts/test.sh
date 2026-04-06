#!/bin/bash
set -e

echo "=== Running CHC Backend Tests ==="
echo ""

uv run pytest tests/ -v --tb=short "$@"
