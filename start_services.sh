#!/bin/bash
# Start all required services for Thandev (Redis, Qdrant)

set -e

echo "=== Starting Thandev Services ==="
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose not found. Please install docker-compose."
    exit 1
fi

# Start Redis and Qdrant using docker-compose
echo "Starting Redis and Qdrant..."
cd "$(dirname "$0")"

# Start only redis and qdrant services
$COMPOSE_CMD up -d redis qdrant

echo ""
echo "Waiting for services to be healthy..."
sleep 5

# Check Redis
echo -n "Checking Redis (port 6379)... "
if docker exec $(docker ps -q -f name=redis) redis-cli ping > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not responding"
fi

# Check Qdrant
echo -n "Checking Qdrant (port 6333)... "
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not responding"
    echo "   Note: Qdrant may take a few seconds to start"
fi

echo ""
echo "=== Services Started ==="
echo ""
echo "Redis:   http://localhost:6379"
echo "Qdrant:  http://localhost:6333"
echo ""
echo "To stop services: docker-compose stop redis qdrant"
echo "To view logs:    docker-compose logs -f redis qdrant"



