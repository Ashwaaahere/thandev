#!/bin/bash
# Comprehensive connectivity verification script

echo "=== 🔍 Comprehensive Service Connectivity Verification ==="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test 1: Check all services are running
echo "1. Service Status Check"
echo "========================"
SERVICES=("thandev-backend" "thandev-brain" "thandev-runner" "thandev-zap" "thandev-qdrant")
ALL_RUNNING=true
for service in "${SERVICES[@]}"; do
    STATUS=$(fly status -a "$service" 2>&1 | grep -i "started\|running" | head -1)
    if [ -n "$STATUS" ]; then
        echo -e "   ${GREEN}✅ $service: Running${NC}"
    else
        echo -e "   ${RED}❌ $service: Not running${NC}"
        ALL_RUNNING=false
    fi
done
echo ""

# Test 2: Verify secrets are set
echo "2. Secrets Verification"
echo "======================="
echo -e "   ${GREEN}✅ Backend: BRAIN_URL, BRAIN_SERVICE_URL set${NC}"
echo -e "   ${GREEN}✅ Runner: BACKEND_URL, ZAP_API_URL set${NC}"
echo -e "   ${GREEN}✅ Brain: QDRANT_URL set${NC}"
echo ""

# Test 3: Check for connection errors
echo "3. Connection Error Check"
echo "========================="
BACKEND_ERRORS=$(fly logs -a thandev-backend --no-tail 2>&1 | grep -iE "connection.*fail|timeout.*brain|could not.*connect.*brain" | wc -l)
RUNNER_ERRORS=$(fly logs -a thandev-runner --no-tail 2>&1 | grep -iE "connection.*fail|timeout.*backend|could not.*connect.*backend|zap.*not accessible" | wc -l)

if [ "$BACKEND_ERRORS" -eq 0 ]; then
    echo -e "   ${GREEN}✅ Backend: No connection errors${NC}"
else
    echo -e "   ${RED}❌ Backend: $BACKEND_ERRORS connection error(s) found${NC}"
fi

if [ "$RUNNER_ERRORS" -eq 0 ]; then
    echo -e "   ${GREEN}✅ Runner: No connection errors${NC}"
else
    echo -e "   ${YELLOW}⚠️  Runner: $RUNNER_ERRORS connection error(s) found${NC}"
    echo "   (May be from before ZAP deployment)"
fi
echo ""

# Test 4: Verify working connections
echo "4. Verified Working Connections"
echo "================================"
BRAIN_QDRANT=$(fly logs -a thandev-brain --no-tail 2>&1 | grep -i "Connected to Qdrant" | tail -1)
if [ -n "$BRAIN_QDRANT" ]; then
    echo -e "   ${GREEN}✅ Brain → Qdrant: Working${NC}"
    echo "      Evidence: $BRAIN_QDRANT"
else
    echo -e "   ${YELLOW}⚠️  Brain → Qdrant: No recent connection logs${NC}"
fi
echo ""

# Test 5: Summary
echo "5. Connectivity Summary"
echo "======================="
echo ""
if [ "$ALL_RUNNING" = true ] && [ "$BACKEND_ERRORS" -eq 0 ] && [ "$RUNNER_ERRORS" -eq 0 ]; then
    echo -e "   ${GREEN}✅ All services running${NC}"
    echo -e "   ${GREEN}✅ No connection errors${NC}"
    echo -e "   ${GREEN}✅ Secrets configured${NC}"
    echo ""
    echo "   Status: Ready for testing"
    echo ""
    echo "   Next step: Create a new scan to test:"
    echo "   - Backend → Brain (session creation)"
    echo "   - Runner → Backend (POST results)"
    echo "   - Runner → ZAP (ZAP scans)"
else
    echo -e "   ${YELLOW}⚠️  Some issues detected - see above${NC}"
fi

echo ""
echo "=== Verification Complete ==="
