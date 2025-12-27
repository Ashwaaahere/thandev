#!/bin/bash
# Test bypass safety by temporarily disabling brain service

echo "🧪 Testing Bypass Safety (Brain Service Disabled)"
echo "=================================================="
echo ""

cd "$(dirname "$0")"
source venv/bin/activate

# Get project details
PROJECT_DATA=$(python << 'EOF'
from app.core.database import SessionLocal
from app.models.project import Project
db = SessionLocal()
try:
    p = db.query(Project).order_by(Project.created_at.desc()).first()
    if p:
        print(f'{p.id}|{p.owner_id}|{p.tenant_id}')
    else:
        print('NO_PROJECT')
finally:
    db.close()
EOF
)

if [ "$PROJECT_DATA" = "NO_PROJECT" ]; then
    echo "❌ No projects found"
    exit 1
fi

PROJECT_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f1)
USER_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f2)
TENANT_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f3)

echo "📋 Using project: $PROJECT_ID"
echo ""

# Test 1: Production should block (even with bypass flag)
echo "Test 1: Production environment with bypass flag"
echo "------------------------------------------------"
echo "Note: This requires the API server to be running with:"
echo "  export ENVIRONMENT=production"
echo "  export THANDEV_DISABLE_PLAN_ENFORCEMENT=1"
echo "  export BRAIN_SERVICE_ENABLED=false  # Disable brain to avoid 500 errors"
echo "  uvicorn app.main:app --reload"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -d "{\"project_id\":\"$PROJECT_ID\",\"scan_level\":\"pro\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo "HTTP Status: $HTTP_CODE"
echo "Response:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
echo ""

if [ "$HTTP_CODE" = "403" ]; then
    if echo "$BODY" | grep -q "plan does not allow"; then
        echo "✅ PASS: Bypass correctly blocked in production"
    else
        echo "⚠️  403 received but message doesn't mention plan restriction"
    fi
elif [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    echo "❌ FAIL: Bypass is NOT safe! Scan was created (should be blocked)"
elif [ "$HTTP_CODE" = "500" ]; then
    echo "⚠️  Server error. Possible causes:"
    echo "   - Brain service not running (set BRAIN_SERVICE_ENABLED=false)"
    echo "   - Celery not running (if using legacy orchestrator)"
    echo "   - Check server logs for actual error"
else
    echo "⚠️  Unexpected status: $HTTP_CODE"
fi

