#!/bin/bash
# Helper script to start Celery worker with correct paths

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set PYTHONPATH to current directory so app module can be found
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Add scanning tools to PATH (required for nuclei, ffuf, dalfox, httpx, etc.)
export PATH="$HOME/.local/thandev-tools/bin:$HOME/go/bin:$HOME/.local/go/bin:$PATH"
export GOPATH="$HOME/go"

# Start Celery worker
# NOTE: Currently all tasks are routed to the default "celery" queue
# (user-specific queues are temporarily disabled until proper multi-queue support is implemented)
echo "Starting Celery worker..."
echo "PYTHONPATH: $PYTHONPATH"
echo "Command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4"
echo ""
echo "Note: All scans are currently routed to the default 'celery' queue"
echo "      - Concurrency=4 allows up to 4 scans to run simultaneously"
echo "      - Per-user sequencing is temporarily disabled"
echo ""

celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4





celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4





celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4





celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4



