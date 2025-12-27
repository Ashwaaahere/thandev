#!/bin/bash
# Test end-to-end scan flow (Celery path)

set -e

echo "=========================================="
echo "Thandev Scan Flow Test (Celery Path)"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$(dirname "$0")/../backend" || exit 1

echo ""
echo "This test requires:"
echo "  1. Backend service running"
echo "  2. Celery worker running"
echo "  3. Database accessible"
echo "  4. Redis accessible"
echo "  5. At least one user and project in database"
echo ""

# Check if backend is running
if ! curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Backend service not running"
    echo "  Start: cd backend && uvicorn app.main:app --reload"
    exit 1
fi

echo -e "${GREEN}✓${NC} Backend service running"

# Check if we can create a test scan via API
echo ""
echo "Note: Full scan flow test requires:"
echo "  - Authenticated user session"
echo "  - Existing project"
echo "  - All tools installed"
echo ""
echo "For manual testing, use the frontend or API directly:"
echo "  POST /api/v1/scans"
echo "  Body: {\"project_id\": \"...\", \"scan_level\": \"basic\"}"
echo ""

echo -e "${YELLOW}⚠${NC} Automated scan flow test requires API authentication"
echo "  See: backend/TESTER_QUICKSTART.md for manual testing steps"

