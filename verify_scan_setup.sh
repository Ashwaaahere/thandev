#!/bin/bash
# Verify scan setup is working correctly

set -e

echo "=== Verifying Scan Setup ==="
echo ""

# 1. Check Redis
echo "1. Redis Connection:"
if redis-cli -p 6379 ping > /dev/null 2>&1; then
    echo "   ✅ Redis is accessible"
    STREAM_LENGTH=$(redis-cli -p 6379 XLEN scan_step_requests 2>/dev/null || echo "0")
    echo "   Stream length: $STREAM_LENGTH messages"
else
    echo "   ❌ Redis is not accessible"
    exit 1
fi

# 2. Check Backend
echo ""
echo "2. Backend Connection:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ Backend is accessible"
    BACKEND_RESPONSE=$(curl -s http://localhost:8000/health)
    echo "   Response: $BACKEND_RESPONSE"
else
    echo "   ❌ Backend is not accessible"
    exit 1
fi

# 3. Check Runner Configuration
echo ""
echo "3. Runner Configuration:"
RUNNER_DIR="/home/ashwath/thandev/services/thandev-runner"
if [ -f "$RUNNER_DIR/.env" ]; then
    echo "   ✅ .env file exists"
    BACKEND_URL=$(grep "^BACKEND_URL=" "$RUNNER_DIR/.env" | cut -d'=' -f2)
    REDIS_URL=$(grep "^REDIS_URL=" "$RUNNER_DIR/.env" | cut -d'=' -f2)
    echo "   BACKEND_URL: $BACKEND_URL"
    echo "   REDIS_URL: $REDIS_URL"
else
    echo "   ❌ .env file not found"
    exit 1
fi

# 4. Check Runner Process
echo ""
echo "4. Runner Process:"
if pgrep -f "python.*app.main" > /dev/null; then
    RUNNER_PID=$(pgrep -f "python.*app.main")
    echo "   ✅ Runner is running (PID: $RUNNER_PID)"
else
    echo "   ⚠️  Runner is not running"
    echo "   Starting runner..."
    cd "$RUNNER_DIR"
    nohup ./start_runner.sh > runner.log 2>&1 &
    sleep 3
    if pgrep -f "python.*app.main" > /dev/null; then
        echo "   ✅ Runner started successfully"
    else
        echo "   ❌ Failed to start runner"
        exit 1
    fi
fi

# 5. Check Consumer Group
echo ""
echo "5. Redis Consumer Group:"
if redis-cli -p 6379 XINFO GROUPS scan_step_requests > /dev/null 2>&1; then
    CONSUMERS=$(redis-cli -p 6379 XINFO GROUPS scan_step_requests | grep consumers | awk '{print $2}')
    PENDING=$(redis-cli -p 6379 XINFO GROUPS scan_step_requests | grep pending | awk '{print $2}')
    echo "   ✅ Consumer group exists"
    echo "   Active consumers: $CONSUMERS"
    echo "   Pending messages: $PENDING"
else
    echo "   ⚠️  Consumer group doesn't exist (will be created when runner consumes)"
fi

# 6. Check Tool Availability
echo ""
echo "6. Tool Availability:"
TOOLS=("nuclei" "nmap" "httpx" "sslscan" "dalfox" "sqlmap")
MISSING_TOOLS=()
for tool in "${TOOLS[@]}"; do
    if command -v "$tool" > /dev/null 2>&1; then
        TOOL_PATH=$(command -v "$tool")
        echo "   ✅ $tool found at: $TOOL_PATH"
    else
        echo "   ⚠️  $tool not found in PATH"
        MISSING_TOOLS+=("$tool")
    fi
done

if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    echo ""
    echo "   ⚠️  Missing tools: ${MISSING_TOOLS[*]}"
    echo "   Some scans may fail if these tools are required"
fi

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Next steps:"
echo "1. Monitor runner logs: tail -f $RUNNER_DIR/runner.log"
echo "2. Trigger a test scan from the UI"
echo "3. Check tool execution in runner logs"
echo ""


