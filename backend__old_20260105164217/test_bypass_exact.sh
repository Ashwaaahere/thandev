#!/bin/bash
# Exact commands to test bypass safety

echo "=========================================="
echo "EXACT COMMANDS TO TEST BYPASS SAFETY"
echo "=========================================="
echo ""
echo "STEP 1: Start API server in Terminal 1"
echo "----------------------------------------"
echo "cd ~/thandev/backend"
echo "source venv/bin/activate"
echo "export ENVIRONMENT=production"
echo "export THANDEV_DISABLE_PLAN_ENFORCEMENT=1"
echo "export BRAIN_SERVICE_ENABLED=false"
echo "uvicorn app.main:app --reload"
echo ""
echo "STEP 2: Test bypass in Terminal 2 (run this command):"
echo "----------------------------------------"
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

echo "curl -s -X POST \"http://localhost:8000/api/scans\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"X-Thandev-User-Id: $USER_ID\" \\"
echo "  -H \"X-Thandev-Tenant-Id: $TENANT_ID\" \\"
echo "  -d '{\"project_id\":\"$PROJECT_ID\",\"scan_level\":\"pro\"}' | python3 -m json.tool"
echo ""
echo "=========================================="
echo "EXPECTED RESULT (with ENVIRONMENT=production):"
echo "----------------------------------------"
echo "HTTP Status: 403"
echo "Response:"
echo "{"
echo "    \"detail\": \"Your plan does not allow 'pro' scans. Allowed levels: basic.\""
echo "}"
echo ""
echo "✅ If you get 403 = Bypass is SAFE (correctly blocked)"
echo "❌ If you get 201 = Bypass is UNSAFE (should be blocked)"
echo ""

