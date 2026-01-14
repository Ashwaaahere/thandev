#!/bin/bash
# Test inter-service connectivity in Fly.io deployment

echo "=== Testing Inter-Service Connectivity ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Backend → Brain
echo "1. Testing Backend → Brain..."
echo "   URL: http://thandev-brain.flycast:8001/healthz"
BACKEND_BRAIN=$(fly logs -a thandev-backend --no-tail 2>&1 | grep -i "brain.*flycast\|Starting brain" | tail -1)
if [ -n "$BACKEND_BRAIN" ]; then
    echo -e "   ${GREEN}✅ Backend has attempted to connect to Brain${NC}"
else
    echo -e "   ${YELLOW}⚠️  No recent Brain connection attempts in logs${NC}"
fi
echo ""

# Test 2: Runner → Backend
echo "2. Testing Runner → Backend..."
echo "   URL: http://thandev-backend.flycast:8000/api/runner/..."
RUNNER_BACKEND=$(fly logs -a thandev-runner --no-tail 2>&1 | grep -iE "POST.*backend.*success\|Posted tool result.*200" | tail -1)
if [ -n "$RUNNER_BACKEND" ]; then
    echo -e "   ${GREEN}✅ Runner successfully connected to Backend${NC}"
else
    RUNNER_BACKEND_ERROR=$(fly logs -a thandev-runner --no-tail 2>&1 | grep -iE "Network error.*backend\|connection.*failed.*backend" | tail -1)
    if [ -n "$RUNNER_BACKEND_ERROR" ]; then
        echo -e "   ${RED}❌ Runner connection to Backend failed${NC}"
        echo "   Error: $RUNNER_BACKEND_ERROR"
    else
        echo -e "   ${YELLOW}⚠️  No recent Backend connection attempts in logs${NC}"
    fi
fi
echo ""

# Test 3: Runner → ZAP
echo "3. Testing Runner → ZAP..."
echo "   URL: http://thandev-zap.flycast:8090"
RUNNER_ZAP=$(fly logs -a thandev-runner --no-tail 2>&1 | grep -i "zap.*accessible\|ZAP API.*accessible" | tail -1)
if [ -n "$RUNNER_ZAP" ]; then
    echo -e "   ${GREEN}✅ Runner successfully connected to ZAP${NC}"
else
    RUNNER_ZAP_ERROR=$(fly logs -a thandev-runner --no-tail 2>&1 | grep -i "zap.*not accessible\|ZAP API.*failed" | tail -1)
    if [ -n "$RUNNER_ZAP_ERROR" ]; then
        echo -e "   ${RED}❌ Runner connection to ZAP failed${NC}"
        echo "   Error: $RUNNER_ZAP_ERROR"
    else
        echo -e "   ${YELLOW}⚠️  No recent ZAP connection attempts in logs${NC}"
    fi
fi
echo ""

# Test 4: Brain → Qdrant
echo "4. Testing Brain → Qdrant..."
echo "   URL: http://thandev-qdrant.flycast:6333"
BRAIN_QDRANT=$(fly logs -a thandev-brain --no-tail 2>&1 | grep -i "qdrant\|vector\|embedding" | tail -1)
if [ -n "$BRAIN_QDRANT" ]; then
    echo -e "   ${GREEN}✅ Brain has attempted to connect to Qdrant${NC}"
else
    echo -e "   ${YELLOW}⚠️  No recent Qdrant connection attempts in logs${NC}"
fi
echo ""

# Test 5: Check all service secrets
echo "5. Verifying Service Secrets..."
echo ""
echo "   Backend secrets (BRAIN_URL):"
BACKEND_BRAIN_SECRET=$(fly secrets list -a thandev-backend 2>&1 | grep BRAIN_URL)
if echo "$BACKEND_BRAIN_SECRET" | grep -q "flycast"; then
    echo -e "   ${GREEN}✅ Backend BRAIN_URL uses .flycast${NC}"
else
    echo -e "   ${RED}❌ Backend BRAIN_URL may not use .flycast${NC}"
fi

echo ""
echo "   Runner secrets (BACKEND_URL, ZAP_API_URL):"
RUNNER_BACKEND_SECRET=$(fly secrets list -a thandev-runner 2>&1 | grep BACKEND_URL)
RUNNER_ZAP_SECRET=$(fly secrets list -a thandev-runner 2>&1 | grep ZAP_API_URL)
if echo "$RUNNER_BACKEND_SECRET" | grep -q "flycast"; then
    echo -e "   ${GREEN}✅ Runner BACKEND_URL uses .flycast${NC}"
else
    echo -e "   ${RED}❌ Runner BACKEND_URL may not use .flycast${NC}"
fi
if echo "$RUNNER_ZAP_SECRET" | grep -q "flycast"; then
    echo -e "   ${GREEN}✅ Runner ZAP_API_URL uses .flycast${NC}"
else
    echo -e "   ${RED}❌ Runner ZAP_API_URL may not use .flycast${NC}"
fi

echo ""
echo "   Brain secrets (QDRANT_URL):"
BRAIN_QDRANT_SECRET=$(fly secrets list -a thandev-brain 2>&1 | grep QDRANT_URL)
if echo "$BRAIN_QDRANT_SECRET" | grep -q "flycast"; then
    echo -e "   ${GREEN}✅ Brain QDRANT_URL uses .flycast${NC}"
else
    echo -e "   ${YELLOW}⚠️  Brain QDRANT_URL may not use .flycast${NC}"
fi

echo ""
echo "=== Connectivity Test Complete ==="
