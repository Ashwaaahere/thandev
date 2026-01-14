#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.fly-local.yml"
ENV_FILE="$ROOT_DIR/.env.fly.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy env-examples/fly-local.env.example to .env.fly.local and adjust values."
  exit 1
fi

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up --build



