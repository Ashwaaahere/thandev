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

# Set DATABASE_URL to backend's database if not already set
# This ensures runner uses the same database as the backend (with all tables)
if [ -z "$DATABASE_URL" ]; then
    # Get absolute path to backend database
    BACKEND_DB_PATH="$(cd "$SCRIPT_DIR/../../backend" && pwd)/thandev.db"
    export DATABASE_URL="sqlite:///$BACKEND_DB_PATH"
fi

echo "Configuration:"
echo "  Consumer Group: $CONSUMER_GROUP"
echo "  Consumer Name: $CONSUMER_NAME"
echo "  Redis URL: ${REDIS_URL:-redis://localhost:6379/0}"
echo "  Database URL: ${DATABASE_URL}"
echo ""

# Run worker loop
echo "Starting worker loop..."
python -m app.tasks



