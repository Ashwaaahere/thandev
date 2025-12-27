#!/bin/bash
# Test infrastructure: Database, Redis, and all services

set -e

echo "=========================================="
echo "Thandev Infrastructure Tests"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $1"
        ((FAILED++))
        return 1
    fi
}

echo ""
echo "1. Testing Database Connection..."
cd "$(dirname "$0")/../backend" || exit 1

# Check if database file exists (SQLite) or connection works (PostgreSQL)
if python3 -c "
from app.core.database import engine
from sqlalchemy import text
try:
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('Database connection successful')
    exit(0)
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
" 2>/dev/null; then
    check "Database connection"
else
    check "Database connection"
    echo "  Run: cd backend && alembic upgrade head"
fi

echo ""
echo "2. Testing Redis Connection..."
if redis-cli ping > /dev/null 2>&1; then
    check "Redis server running"
    
    # Check Redis streams
    if redis-cli EXISTS scan_step_requests > /dev/null 2>&1 || redis-cli EXISTS scan_step_results > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis streams accessible"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠${NC} Redis streams not yet created (will be created on first use)"
    fi
else
    check "Redis server running"
    echo "  Start Redis: redis-server"
fi

echo ""
echo "3. Testing Backend Service..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    check "Backend service running (port 8000)"
else
    echo -e "${YELLOW}⚠${NC} Backend service not running on port 8000"
    echo "  Start: cd backend && uvicorn app.main:app --reload"
fi

echo ""
echo "4. Testing Brain Service..."
if curl -s http://localhost:8001/v1/health > /dev/null 2>&1; then
    check "Brain service running (port 8001)"
    
    # Test catalog endpoint
    if curl -s http://localhost:8001/v1/catalog > /dev/null 2>&1; then
        check "Brain catalog endpoint accessible"
    else
        check "Brain catalog endpoint accessible"
    fi
else
    echo -e "${YELLOW}⚠${NC} Brain service not running on port 8001"
    echo "  Start: cd services/thandev-brain && uvicorn app.main:app --port 8001"
fi

echo ""
echo "5. Testing Runner Service..."
# Check if runner process is running
if pgrep -f "thandev-runner" > /dev/null 2>&1 || pgrep -f "app/main.py" > /dev/null 2>&1; then
    check "Runner service process running"
else
    echo -e "${YELLOW}⚠${NC} Runner service not running"
    echo "  Start: cd services/thandev-runner && python app/main.py"
fi

echo ""
echo "6. Testing Celery Worker..."
if pgrep -f "celery.*worker" > /dev/null 2>&1; then
    check "Celery worker running"
else
    echo -e "${YELLOW}⚠${NC} Celery worker not running"
    echo "  Start: cd backend && celery -A app.tasks.celery_app worker --loglevel=info"
fi

echo ""
echo "7. Checking Environment Variables..."
cd "$(dirname "$0")/../backend" || exit 1
if [ -f .env ]; then
    check "Backend .env file exists"
    
    # Check critical variables
    if grep -q "DATABASE_URL" .env && grep -q "REDIS_URL" .env; then
        check "Critical environment variables set"
    else
        echo -e "${YELLOW}⚠${NC} Some environment variables may be missing"
    fi
else
    echo -e "${YELLOW}⚠${NC} Backend .env file not found"
fi

echo ""
echo "=========================================="
echo "Summary: ${GREEN}${PASSED} passed${NC}, ${RED}${FAILED} failed${NC}"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi

