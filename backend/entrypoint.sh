#!/bin/bash
set -e

# Wait for database to be ready (only for PostgreSQL)
if [[ "$DATABASE_URL" == postgresql* ]] || [[ "$DATABASE_URL" == postgres* ]]; then
  echo "Waiting for PostgreSQL database to be ready..."
  RETRIES=10
  until python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')" 2>/dev/null || [ $RETRIES -eq 0 ]; do
    echo "Waiting for postgres, $RETRIES remaining attempts..."
    RETRIES=$((RETRIES-1))
    sleep 2
  done

  if [ $RETRIES -eq 0 ]; then
    echo "Failed to connect to database after 20 seconds"
    exit 1
  fi

  echo "Database is ready!"
else
  echo "Using SQLite database (no connection wait needed)"
fi

# If command arguments are provided, execute them and exit
# This is used by Fly.io release_command to run migrations
if [ $# -gt 0 ]; then
  echo "Executing command: $@"
  if echo "$*" | grep -q "&&"; then
    exec /bin/bash -c "$*"
  else
    exec "$@"
  fi
fi

# Run database migrations before starting the server
echo "Running database migrations..."
cd /app
python -m alembic upgrade head || {
  echo "Warning: Migrations failed, but continuing startup..."
}
echo "Migrations completed!"

# ----------------------------
# Runtime mode
# ----------------------------
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-1}"

echo "Starting API server:"
echo "  - Bind: 0.0.0.0:${PORT} (dual-stack via IPv4)"
echo "  - Workers: ${WORKERS}"

# Start gunicorn with uvicorn workers
# Bind to 0.0.0.0 - Fly.io proxy handles IPv6/IPv4 translation
# The connection reset issue is likely application-level, not network-level
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT} \
  --workers ${WORKERS} \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
