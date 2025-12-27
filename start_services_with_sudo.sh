#!/bin/bash
# Start Redis and Qdrant with sudo (if user not in docker group)

set -e

echo "=== Starting Redis and Qdrant (with sudo) ==="
echo ""

# Check Redis
echo -n "Checking Redis (port 6379)... "
# Try multiple methods to check Redis (in order of preference)
REDIS_RUNNING=false
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "✅ Already running"
    REDIS_RUNNING=true
elif timeout 1 bash -c "echo PING | nc localhost 6379" 2>/dev/null | grep -q PONG; then
    echo "✅ Already running (verified via netcat)"
    REDIS_RUNNING=true
elif timeout 1 bash -c "echo > /dev/tcp/localhost/6379" 2>/dev/null; then
    # Port is open, check if it's our container
    if docker ps 2>/dev/null | grep -q thandev-redis || sudo docker ps 2>/dev/null | grep -q thandev-redis; then
        echo "✅ Already running (port open)"
        REDIS_RUNNING=true
    else
        echo "⚠️  Port open but container not found"
        REDIS_RUNNING=false
    fi
else
    echo "❌ Not running"
    REDIS_RUNNING=false
fi

# Check Qdrant
echo -n "Checking Qdrant (port 6333)... "
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Already running"
    QDRANT_RUNNING=true
else
    echo "❌ Not running"
    QDRANT_RUNNING=false
fi

echo ""

# Start Redis
if [ "$REDIS_RUNNING" = false ]; then
    echo "Starting Redis with Docker (sudo)..."
    sudo docker start thandev-redis 2>/dev/null || \
    sudo docker run -d --name thandev-redis -p 6379:6379 redis:7-alpine || \
    echo "⚠️  Failed to start Redis"
fi

# Start Qdrant
if [ "$QDRANT_RUNNING" = false ]; then
    echo "Starting Qdrant with Docker (sudo)..."
    sudo docker start thandev-qdrant 2>/dev/null || \
    sudo docker run -d --name thandev-qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest || \
    echo "⚠️  Failed to start Qdrant"
fi

echo ""
echo "Waiting 3 seconds for services to start..."
sleep 3

# Verify
echo ""
echo "=== Verification ==="
echo -n "Redis (port 6379): "
# Try multiple methods to verify Redis (no sudo required for checks)
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "✅ Running"
elif timeout 1 bash -c "echo PING | nc localhost 6379" 2>/dev/null | grep -q PONG; then
    echo "✅ Running (verified via netcat)"
elif timeout 1 bash -c "echo > /dev/tcp/localhost/6379" 2>/dev/null; then
    # Check if container exists (try without sudo first)
    if docker ps 2>/dev/null | grep -q thandev-redis; then
        echo "✅ Running (port open, container running)"
    elif sudo docker ps 2>/dev/null | grep -q thandev-redis; then
        echo "✅ Running (port open, container running)"
    else
        echo "⚠️  Port open but container status unknown"
    fi
else
    echo "❌ Not responding"
    echo "   Port 6379 is not accessible"
fi

echo -n "Qdrant (port 6333): "
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not responding (may need a few more seconds)"
fi

echo ""
echo "=== Done ==="
echo ""
echo "Note: To avoid using sudo, add your user to docker group:"
echo "  sudo usermod -aG docker $USER"
echo "  (then logout and login again)"



