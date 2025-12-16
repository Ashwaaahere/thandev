#!/bin/bash
# Start Redis and Qdrant with sudo (if user not in docker group)

set -e

echo "=== Starting Redis and Qdrant (with sudo) ==="
echo ""

# Check Redis
echo -n "Checking Redis (port 6379)... "
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "✅ Already running"
    REDIS_RUNNING=true
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
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not responding"
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



