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

# Note: Migrations are handled by Fly.io release_command (see fly.toml)
# This ensures migrations run once per deploy, not on every container restart

# Start the application
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

