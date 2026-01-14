#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.fly-local.yml"
ENV_FILE="$ROOT_DIR/.env.fly.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy env-examples/fly-local.env.example to .env.fly.local and adjust values."
  exit 1
fi

echo "Stopping and removing services/volumes..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v

echo "Starting infra (postgres, redis, qdrant)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres redis qdrant

echo "Waiting for postgres to be healthy..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" wait postgres

echo "Running migrations in backend (alembic upgrade head)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm backend ./entrypoint.sh alembic upgrade head

echo "Infra ready. You can now start the full stack with scripts/up_fly_local.sh"



