#!/bin/bash
# Start Thandev Brain Service
# Assumes virtual environment is activated

set -e

echo "Starting Thandev Brain Service..."

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not detected. Activate it first:"
    echo "  cd services/thandev-brain"
    echo "  source venv/bin/activate  # or .venv/bin/activate"
    exit 1
fi

# Check if Qdrant is running
if ! curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "Warning: Qdrant not running on port 6333"
    echo "Start it with: docker run -d -p 6333:6333 qdrant/qdrant:latest"
    echo "Or check if it's already running on a different port"
fi

# Start brain service
echo "Starting brain service on port 8001..."
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload




