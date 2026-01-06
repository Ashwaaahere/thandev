#!/bin/bash
# Test script for production bypass safety

set -e

echo "🧪 Testing Production Bypass Safety"
echo "==================================="
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
    echo "❌ No projects found in database"
    exit 1
fi

PROJECT_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f1)
USER_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f2)
TENANT_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f3)

echo "📋 Project Details:"
echo "   Project ID: $PROJECT_ID"
echo "   User ID: $USER_ID"
echo "   Tenant ID: $TENANT_ID"
echo ""

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ API server is not running on http://localhost:8000"
    echo ""
    echo "Please start the server first:"
    echo "   cd ~/thandev/backend"
    echo "   source venv/bin/activate"
    echo "   export ENVIRONMENT=production"
    echo "   export THANDEV_DISABLE_PLAN_ENFORCEMENT=1"
    echo "   uvicorn app.main:app --reload"
    exit 1
fi

echo "✅ API server is running"
echo ""

# Test the scan creation
echo "🧪 Testing PRO scan creation with production env..."
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -d "{\"project_id\":\"$PROJECT_ID\",\"scan_level\":\"pro\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo "HTTP Status Code: $HTTP_CODE"
echo "Response Body:"
echo "$BODY" | python -m json.tool 2>/dev/null || echo "$BODY"
echo ""

# Check result
if [ "$HTTP_CODE" = "403" ]; then
    echo "✅ PASS: Bypass correctly blocked in production (403 Forbidden)"
    if echo "$BODY" | grep -q "plan does not allow"; then
        echo "✅ PASS: Error message indicates plan restriction"
    else
        echo "⚠️  WARNING: 403 received but message doesn't mention plan restriction"
    fi
    exit 0
elif [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    echo "❌ FAIL: Bypass is NOT safe! Scan was created in production (should be blocked)"
    exit 1
elif [ "$HTTP_CODE" = "500" ]; then
    echo "⚠️  Server error (500). Check server logs for details."
    echo ""
    echo "Common causes:"
    echo "  - Brain service not running (if BRAIN_REQUIRED=true)"
    echo "  - Database connection issue"
    echo "  - Missing environment variables"
    echo ""
    echo "Check server logs in the terminal where uvicorn is running."
    exit 1
else
    echo "⚠️  Unexpected status code: $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi

