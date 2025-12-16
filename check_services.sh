#!/bin/bash
# Check status of all Thandev services

echo "=== Thandev Services Status ==="
echo ""

# Check Qdrant
echo "Qdrant (port 6333):"
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "  ✓ Running"
    curl -s http://localhost:6333/health | python3 -m json.tool 2>/dev/null || echo "  Response: OK"
else
    echo "  ✗ Not running"
    echo "  Start with: docker run -d -p 6333:6333 qdrant/qdrant:latest"
fi
echo ""

# Check Brain Service
echo "Brain Service (port 8001):"
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "  ✓ Running"
    curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null || echo "  Response: OK"
else
    echo "  ✗ Not running"
    echo "  Start with: cd services/thandev-brain && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8001"
fi
echo ""

# Check Core Backend
echo "Core Backend (port 8000):"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  ✓ Running"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "  Response: OK"
else
    echo "  ✗ Not running"
    echo "  Start with: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"
fi
echo ""

# Check Redis
echo "Redis (port 6379):"
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "  ✓ Running"
else
    echo "  ✗ Not running (or redis-cli not installed)"
fi
echo ""

# Check PostgreSQL
echo "PostgreSQL (port 5432):"
if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "  ✓ Running"
else
    echo "  ✗ Not running (or pg_isready not installed)"
fi
echo ""

echo "=== Status Check Complete ==="




