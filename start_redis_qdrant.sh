#!/bin/bash
# Start Redis and Qdrant services
# Supports both Docker and systemd

set -e

echo "=== Starting Redis and Qdrant ==="
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
    echo "Starting Redis..."
    
    # Try systemd first
    if systemctl is-active --quiet redis 2>/dev/null || systemctl is-active --quiet redis-server 2>/dev/null; then
        echo "Redis service found but not responding. Restarting..."
        sudo systemctl restart redis 2>/dev/null || sudo systemctl restart redis-server 2>/dev/null || true
    elif command -v docker > /dev/null 2>&1; then
        echo "Starting Redis with Docker..."
        # Try to start existing container first, then create new one
        docker start thandev-redis 2>/dev/null || \
        docker run -d --name thandev-redis -p 6379:6379 redis:7-alpine 2>/dev/null || \
        echo "⚠️  Failed to start Redis. Please check Docker daemon."
    else
        echo "⚠️  Cannot start Redis automatically."
        echo "   Options:"
        echo "   1. Start Docker: sudo snap start docker (if using snap)"
        echo "   2. Install Redis: sudo apt install redis-server"
        echo "   3. Start manually: redis-server"
        echo "   4. Start with Docker: docker run -d --name thandev-redis -p 6379:6379 redis:7-alpine"
    fi
fi

# Start Qdrant
if [ "$QDRANT_RUNNING" = false ]; then
    echo "Starting Qdrant..."
    
    if command -v docker > /dev/null 2>&1; then
        echo "Starting Qdrant with Docker..."
        # Try to start existing container first, then create new one
        docker start thandev-qdrant 2>/dev/null || \
        docker run -d --name thandev-qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest 2>/dev/null || \
        echo "⚠️  Failed to start Qdrant. Please check Docker daemon."
    else
        echo "⚠️  Cannot start Qdrant automatically (requires Docker)."
        echo "   Options:"
        echo "   1. Start Docker: sudo snap start docker (if using snap)"
        echo "   2. Start manually: docker run -d -p 6333:6333 qdrant/qdrant:latest"
    fi
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

