#!/bin/bash
# Start Thandev Runner Service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Starting Thandev Runner Service ==="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    touch venv/.installed
fi

# Set default environment variables if not set
export CONSUMER_GROUP=${CONSUMER_GROUP:-runner-workers}
export CONSUMER_NAME=${CONSUMER_NAME:-${HOSTNAME:-runner-1}}

# CRITICAL: Runner must use the SAME database as backend
# Backend uses PostgreSQL by default, so runner should too
# Force-set to PostgreSQL to override .env file
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/thandev"

echo "Configuration:"
echo "  Consumer Group: $CONSUMER_GROUP"
echo "  Consumer Name: $CONSUMER_NAME"
echo "  Redis URL: ${REDIS_URL:-redis://localhost:6379/0}"
echo "  Database URL: $DATABASE_URL"
echo ""

# Run worker loop
echo "Starting worker loop..."
python -m app.tasks



