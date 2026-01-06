#!/bin/bash
# Start Thandev Brain Service
# Assumes virtual environment is activated

set -e

echo "Starting Thandev Brain Service..."

# In containerized env we don't rely on an activated venv; just run uvicorn
# Optional: set SKIP_VENV_CHECK=1 to bypass locally
if [ -z "$VIRTUAL_ENV" ] && [ "${SKIP_VENV_CHECK:-0}" != "1" ]; then
    echo "Warning: Virtual environment not detected. Continuing without venv."
fi

# Check if Qdrant is reachable (best-effort)
if ! curl -s http://qdrant:6333/health > /dev/null 2>&1; then
    echo "Warning: Qdrant not reachable at qdrant:6333 (continuing anyway)"
fi

echo "Starting brain service on port 8001..."
uvicorn app.main:app --host 0.0.0.0 --port 8001




