#!/bin/bash
# Fix Redis container issues

set -e

echo "=== Fixing Redis ==="
echo ""

# Check if Redis container exists
if sudo docker ps -a | grep -q thandev-redis; then
    echo "Redis container exists. Checking status..."
    
    # Check if it's running
    if sudo docker ps | grep -q thandev-redis; then
        echo "✅ Redis container is running"
        echo "Checking logs for issues..."
        sudo docker logs --tail 20 thandev-redis
    else
        echo "❌ Redis container exists but is not running"
        echo "Starting Redis container..."
        sudo docker start thandev-redis
        sleep 2
    fi
else
    echo "Redis container doesn't exist. Creating new one..."
    sudo docker run -d --name thandev-redis -p 6379:6379 redis:7-alpine
    sleep 2
fi

# Check if port is accessible
echo ""
echo "Testing Redis connection..."
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "✅ Redis is responding via redis-cli"
elif command -v redis-cli > /dev/null 2>&1; then
    echo "⚠️  redis-cli available but Redis not responding"
    echo "Checking container logs..."
    sudo docker logs --tail 10 thandev-redis
else
    echo "⚠️  redis-cli not installed. Testing with docker exec..."
    if sudo docker exec thandev-redis redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis is working inside container"
        echo "⚠️  Port may not be exposed correctly"
    else
        echo "❌ Redis is not responding inside container"
        echo "Container logs:"
        sudo docker logs --tail 20 thandev-redis
    fi
fi

# Test with curl if available
echo ""
echo "Testing port 6379..."
if timeout 1 bash -c "echo > /dev/tcp/localhost/6379" 2>/dev/null; then
    echo "✅ Port 6379 is open"
else
    echo "❌ Port 6379 is not accessible"
    echo "Checking container port mapping..."
    sudo docker port thandev-redis
fi

# Final verification
echo ""
echo "=== Final Status ==="
if sudo docker ps | grep -q thandev-redis; then
    echo "Container: ✅ Running"
    if sudo docker exec thandev-redis redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "Redis service: ✅ Working"
    else
        echo "Redis service: ❌ Not responding"
    fi
else
    echo "Container: ❌ Not running"
fi

echo ""
echo "=== Done ==="

