#!/bin/bash
# Fix scan execution issues for local development
# This script ensures all services are properly configured

set -e

echo "=== Fixing Scan Execution Issues ==="
echo ""

# 1. Check Redis connection
echo "1. Checking Redis connection..."
if redis-cli -p 6379 ping > /dev/null 2>&1; then
    echo "   ✅ Redis is running on port 6379"
else
    echo "   ❌ Redis is not running on port 6379"
    echo "   Starting Redis..."
    redis-server --daemonize yes --port 6379 || echo "   ⚠️  Failed to start Redis. Please start it manually."
fi

# 2. Check Backend connection
echo ""
echo "2. Checking Backend connection..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Backend is running on port 8000"
else
    echo "   ❌ Backend is not running on port 8000"
    echo "   Please start the backend: cd backend && ./start.sh"
    exit 1
fi

# 3. Check Runner configuration
echo ""
echo "3. Checking Runner configuration..."
RUNNER_DIR="/home/ashwath/thandev/services/thandev-runner"

# Check if .env exists, create if not
if [ ! -f "$RUNNER_DIR/.env" ]; then
    echo "   Creating .env file for runner..."
    cat > "$RUNNER_DIR/.env" << EOF
# Runner Service Configuration
BACKEND_URL=http://localhost:8000
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://postgres:6ySBsM6lRK8JSMQu@db.kooxcykmlwonxqdushgt.supabase.co:5432/postgres?sslmode=require
RUNNER_API_TOKEN=
CONSUMER_GROUP=runner-workers
CONSUMER_NAME=runner-1
EOF
    echo "   ✅ Created .env file"
else
    echo "   ✅ .env file exists"
fi

# 4. Ensure RUNNER_API_TOKEN matches (or is unset for dev)
echo ""
echo "4. Checking RUNNER_API_TOKEN configuration..."
BACKEND_ENV="/home/ashwath/thandev/backend/.env"
if [ -f "$BACKEND_ENV" ]; then
    BACKEND_TOKEN=$(grep "^RUNNER_API_TOKEN=" "$BACKEND_ENV" | cut -d'=' -f2 || echo "")
    RUNNER_TOKEN=$(grep "^RUNNER_API_TOKEN=" "$RUNNER_DIR/.env" | cut -d'=' -f2 || echo "")
    
    if [ -z "$BACKEND_TOKEN" ] && [ -z "$RUNNER_TOKEN" ]; then
        echo "   ✅ Both backend and runner have RUNNER_API_TOKEN unset (dev mode)"
    elif [ "$BACKEND_TOKEN" = "$RUNNER_TOKEN" ] && [ -n "$BACKEND_TOKEN" ]; then
        echo "   ✅ RUNNER_API_TOKEN matches between backend and runner"
    else
        echo "   ⚠️  RUNNER_API_TOKEN mismatch or partially set"
        echo "   Setting both to empty for dev mode..."
        if grep -q "^RUNNER_API_TOKEN=" "$BACKEND_ENV"; then
            sed -i 's/^RUNNER_API_TOKEN=.*/RUNNER_API_TOKEN=/' "$BACKEND_ENV"
        else
            echo "RUNNER_API_TOKEN=" >> "$BACKEND_ENV"
        fi
        if grep -q "^RUNNER_API_TOKEN=" "$RUNNER_DIR/.env"; then
            sed -i 's/^RUNNER_API_TOKEN=.*/RUNNER_API_TOKEN=/' "$RUNNER_DIR/.env"
        else
            echo "RUNNER_API_TOKEN=" >> "$RUNNER_DIR/.env"
        fi
        echo "   ✅ Fixed RUNNER_API_TOKEN configuration"
    fi
else
    echo "   ⚠️  Backend .env not found, skipping token check"
fi

# 5. Check if runner is running
echo ""
echo "5. Checking Runner process..."
if pgrep -f "python.*app.main" > /dev/null; then
    echo "   ✅ Runner process is running"
    echo "   To restart runner: cd $RUNNER_DIR && ./start_runner.sh"
else
    echo "   ❌ Runner process is not running"
    echo "   Starting runner..."
    cd "$RUNNER_DIR"
    nohup ./start_runner.sh > runner.log 2>&1 &
    echo "   ✅ Runner started (check runner.log for output)"
fi

# 6. Verify Redis stream consumer group
echo ""
echo "6. Verifying Redis stream consumer group..."
if redis-cli -p 6379 XINFO GROUPS scan_step_requests > /dev/null 2>&1; then
    echo "   ✅ Consumer group exists"
    CONSUMERS=$(redis-cli -p 6379 XINFO GROUPS scan_step_requests | grep consumers | awk '{print $2}')
    echo "   Active consumers: $CONSUMERS"
else
    echo "   ⚠️  Consumer group doesn't exist yet (will be created when runner starts)"
fi

echo ""
echo "=== Configuration Check Complete ==="
echo ""
echo "Next steps:"
echo "1. Verify runner is consuming messages: tail -f $RUNNER_DIR/runner.log"
echo "2. Check backend logs for tool result POSTs"
echo "3. Trigger a test scan and monitor progress"
echo ""


