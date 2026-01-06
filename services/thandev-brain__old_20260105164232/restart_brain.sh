#!/bin/bash
# Restart Thandev Brain Service
# Stops any existing instance and starts a fresh one

set -e

echo "=== Restarting Thandev Brain Service ==="
echo ""

# Find and kill any existing brain service processes
echo "Checking for existing brain service processes..."
BRAIN_PIDS=$(ps aux | grep -E "uvicorn.*app.main:app.*8001|thandev-brain.*8001" | grep -v grep | awk '{print $2}' || true)

if [ -n "$BRAIN_PIDS" ]; then
    echo "Found existing brain service processes: $BRAIN_PIDS"
    echo "Stopping them..."
    for pid in $BRAIN_PIDS; do
        kill -TERM $pid 2>/dev/null || kill -9 $pid 2>/dev/null || true
    done
    sleep 2
    echo "✅ Stopped existing processes"
else
    echo "No existing brain service processes found"
fi

# Check if port 8001 is still in use
if lsof -i :8001 > /dev/null 2>&1 || ss -tulpn | grep -q ":8001" 2>/dev/null; then
    echo "⚠️  Port 8001 is still in use. Waiting 3 seconds..."
    sleep 3
    if lsof -i :8001 > /dev/null 2>&1 || ss -tulpn | grep -q ":8001" 2>/dev/null; then
        echo "❌ Port 8001 is still in use. Please manually stop the process using it."
        echo "   Run: lsof -i :8001  or  ss -tulpn | grep 8001"
        exit 1
    fi
fi

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        echo "❌ Virtual environment not found. Please create it first:"
        echo "   python3 -m venv venv"
        echo "   source venv/bin/activate"
        echo "   pip install -r requirements.txt"
        exit 1
    fi
fi

# Check if Redis is running
echo ""
echo "Checking dependencies..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Warning: Redis not running on port 6379"
    echo "   Start it with: redis-cli ping  (or ./start_redis_qdrant.sh)"
fi

# Check if Qdrant is running
if ! curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "⚠️  Warning: Qdrant not running on port 6333"
    echo "   Start it with: docker run -d -p 6333:6333 qdrant/qdrant:latest"
fi

# Start brain service
echo ""
echo "Starting brain service on port 8001..."
echo "Press Ctrl+C to stop"
echo ""
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

