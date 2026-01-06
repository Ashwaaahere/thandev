#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.fly.local"

backend_url=${BACKEND_URL:-http://localhost:8000}
brain_url=${BRAIN_URL:-http://localhost:8001}

echo "Backend health ($backend_url/health):"
curl -sf "$backend_url/health" || { echo "Backend health check failed"; exit 1; }
echo

echo "Brain health ($brain_url/health or /):"
if ! curl -sf "$brain_url/health"; then
  curl -sf "$brain_url" || true
fi
echo

echo "Redis ping (compose redis service)..."
if command -v docker >/dev/null 2>&1; then
  docker exec thandev-redis-1 redis-cli ping || true
fi

echo "Health checks attempted."


