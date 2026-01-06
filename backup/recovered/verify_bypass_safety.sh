#!/bin/bash
# Verification script for plan bypass safety

set -e

echo "🔍 Verifying Plan Bypass Safety"
echo "================================"
echo ""

# Get a real project ID from database
echo "📋 Fetching a real project ID from database..."
cd "$(dirname "$0")"
source venv/bin/activate

PROJECT_DATA=$(python -c "
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
")

if [ "$PROJECT_DATA" = "NO_PROJECT" ]; then
    echo "❌ No projects found in database. Please create a project first."
    exit 1
fi

PROJECT_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f1)
USER_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f2)
TENANT_ID=$(echo "$PROJECT_DATA" | cut -d'|' -f3)

echo "✅ Found project: $PROJECT_ID"
echo "   User ID: $USER_ID"
echo "   Tenant ID: $TENANT_ID"
echo ""

# Test 1: Production environment should block bypass
echo "🧪 Test 1: Production environment with bypass flag"
echo "---------------------------------------------------"
echo "Setting ENVIRONMENT=production and THANDEV_DISABLE_PLAN_ENFORCEMENT=1"
echo ""

# Note: This test requires the API server to be running with production env
echo "⚠️  To test this, start your API server with:"
echo "   export ENVIRONMENT=production"
echo "   export THANDEV_DISABLE_PLAN_ENFORCEMENT=1"
echo "   uvicorn app.main:app --reload"
echo ""
echo "Then in another terminal, run:"
echo "   curl -s -X POST 'http://localhost:8000/api/scans' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -H 'X-Thandev-User-Id: $USER_ID' \\"
echo "     -H 'X-Thandev-Tenant-Id: $TENANT_ID' \\"
echo "     -d '{\"project_id\":\"$PROJECT_ID\",\"scan_level\":\"pro\"}' | jq"
echo ""
echo "✅ Expected: 403 Forbidden with 'Your plan does not allow' message"
echo "❌ If it succeeds, the bypass guard is unsafe"
echo ""

# Test 2: Verify Python environment
echo "🧪 Test 2: Python Environment Check"
echo "-----------------------------------"
echo "Checking if SQLAlchemy is available in venv..."
echo ""

if python -c "import sqlalchemy; print('SQLAlchemy version:', sqlalchemy.__version__)" 2>/dev/null; then
    echo "✅ SQLAlchemy is available"
else
    echo "❌ SQLAlchemy not found. Installing dependencies..."
    pip install -r requirements.txt
fi
echo ""

# Test 3: Tool subset test instructions
echo "🧪 Test 3: Tool Subset Smoke Test"
echo "---------------------------------"
echo "To run the tool subset test:"
echo ""
echo "   cd ~/thandev/backend"
echo "   source venv/bin/activate"
echo ""
echo "   export RUN_MANUAL_INTEGRATION=1"
echo "   export THANDEV_PROJECT_ID=\"$PROJECT_ID\""
echo "   export THANDEV_PIPELINE_TOOLS=\"httpx,nuclei\""
echo "   export THANDEV_FAST_MANUAL=1"
echo ""
echo "   pytest test_scan_pipeline.py::test_basic_scan -vv -s"
echo ""
echo "✅ Expected:"
echo "   - Only httpx + nuclei actually run"
echo "   - Other tools end as 'skipped' (not 'pending forever') after scan completes"
echo ""

echo "================================"
echo "✅ Verification script complete"
echo ""
echo "Next steps:"
echo "1. Start API server with production env to test bypass safety"
echo "2. Run tool subset test with the commands above"

