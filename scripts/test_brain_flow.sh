#!/bin/bash
# Test brain-managed scan flow

set -e

echo "=========================================="
echo "Thandev Brain Flow Test"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$(dirname "$0")/.." || exit 1

echo ""
echo "1. Testing Brain Service..."
if curl -s http://localhost:8001/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Brain service running"
    
    # Test catalog
    if curl -s http://localhost:8001/v1/catalog | jq . > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Brain catalog accessible"
    else
        echo -e "${YELLOW}⚠${NC} Brain catalog may not return valid JSON"
    fi
else
    echo -e "${RED}✗${NC} Brain service not running"
    echo "  Start: cd services/thandev-brain && uvicorn app.main:app --port 8001"
    exit 1
fi

echo ""
echo "2. Testing Redis Streams..."
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Redis accessible"
    
    # Check if streams exist (they may not exist yet)
    if redis-cli EXISTS scan_step_requests > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} scan_step_requests stream exists"
    else
        echo -e "${YELLOW}⚠${NC} scan_step_requests stream not created yet (will be created on first use)"
    fi
else
    echo -e "${RED}✗${NC} Redis not accessible"
    exit 1
fi

echo ""
echo "3. Testing Runner Service..."
if pgrep -f "thandev-runner" > /dev/null 2>&1 || pgrep -f "services/thandev-runner" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Runner service process running"
else
    echo -e "${YELLOW}⚠${NC} Runner service not running"
    echo "  Start: cd services/thandev-runner && python app/main.py"
fi

echo ""
echo "4. Testing Brain-Backend Integration..."
cd backend || exit 1
if python3 -c "
from app.services.brain_client import get_brain_client
from app.core.config import settings
if settings.BRAIN_SERVICE_ENABLED:
    print('Brain service enabled in config')
    try:
        client = get_brain_client()
        print('Brain client created successfully')
    except Exception as e:
        print(f'Brain client creation failed: {e}')
        exit(1)
else:
    print('Brain service disabled in config')
    exit(0)
" 2>&1; then
    echo -e "${GREEN}✓${NC} Brain client can be created"
else
    echo -e "${YELLOW}⚠${NC} Brain client creation issue"
fi

echo ""
echo "Note: Full brain flow test requires:"
echo "  - Brain service running"
echo "  - Runner service running"
echo "  - Redis streams configured"
echo "  - Backend configured with BRAIN_SERVICE_ENABLED=true"
echo "  - Creating a scan via API will trigger brain session"
echo ""

