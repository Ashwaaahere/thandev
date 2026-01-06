# Verification Instructions

This document provides step-by-step instructions to verify all the fixes.

## 1. Verify Plan Bypass Safety

### Test: Production Environment Should Block Bypass

**Terminal 1 - Start API server with production env:**
```bash
cd ~/thandev/backend
source venv/bin/activate
export ENVIRONMENT=production
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
uvicorn app.main:app --reload
```

**Terminal 2 - Attempt PRO scan:**
```bash
# Get project ID first (or use the one from verify_bypass_safety.sh output)
cd ~/thandev/backend
source venv/bin/activate

# Get project details
python -c "
from app.core.database import SessionLocal
from app.models.project import Project
db = SessionLocal()
try:
    p = db.query(Project).order_by(Project.created_at.desc()).first()
    if p:
        print(f'PROJECT_ID={p.id}')
        print(f'USER_ID={p.owner_id}')
        print(f'TENANT_ID={p.tenant_id}')
    else:
        print('No projects found')
finally:
    db.close()
"

# Then test the API (replace with actual IDs from above)
curl -s -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <USER_ID>" \
  -H "X-Thandev-Tenant-Id: <TENANT_ID>" \
  -d '{"project_id":"<PROJECT_ID>","scan_level":"pro"}' | jq
```

**✅ Expected Result:**
```json
{
  "detail": "Your plan does not allow 'pro' scans. Allowed levels: basic."
}
```
Status code: `403 Forbidden`

**❌ If it succeeds (200/201), the bypass guard is unsafe!**

### Test: Dev/Test Environment Should Allow Bypass

**Terminal 1 - Start API server with dev env:**
```bash
cd ~/thandev/backend
source venv/bin/activate
export ENVIRONMENT=dev
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
uvicorn app.main:app --reload
```

**Terminal 2 - Attempt PRO scan (should succeed):**
```bash
# Use same curl command as above
# Should return 200/201 with scan created
```

**✅ Expected:** Scan creation succeeds (bypass working in dev)

---

## 2. Verify Python Environment

**Check SQLAlchemy is available:**
```bash
cd ~/thandev/backend
source venv/bin/activate

which python
python -c "import sqlalchemy; print('SQLAlchemy version:', sqlalchemy.__version__)"
```

**✅ Expected:** Shows SQLAlchemy version (e.g., `2.0.35`)

**If it fails:**
```bash
pip install -r requirements.txt
```

---

## 3. Verify Tool Subset Filtering

**Run tool subset smoke test:**
```bash
cd ~/thandev/backend
source venv/bin/activate

# Get a real project ID
PROJECT_ID=$(python -c "
from app.core.database import SessionLocal
from app.models.project import Project
db = SessionLocal()
try:
    p = db.query(Project).order_by(Project.created_at.desc()).first()
    print(p.id if p else '')
finally:
    db.close()
")

if [ -z "$PROJECT_ID" ]; then
    echo "❌ No projects found. Create a project first."
    exit 1
fi

export RUN_MANUAL_INTEGRATION=1
export THANDEV_PROJECT_ID="$PROJECT_ID"
export THANDEV_PIPELINE_TOOLS="httpx,nuclei"
export THANDEV_FAST_MANUAL=1

pytest test_scan_pipeline.py::test_basic_scan -vv -s
```

**✅ Expected Results:**
- Only `httpx` and `nuclei` actually execute
- Other tools (like `sslscan`, `dalfox`, etc.) show as `skipped` with `error_code: "filtered_out"`
- No tools remain in `pending` state after scan completes
- Scan completes successfully

**Verify in API:**
```bash
# After scan completes, check tool statuses
curl -s "http://localhost:8000/api/scans/<SCAN_ID>" \
  -H "X-Thandev-User-Id: <USER_ID>" \
  -H "X-Thandev-Tenant-Id: <TENANT_ID>" \
  | jq '.tool_statuses[] | select(.status == "skipped")'
```

**Expected output:**
```json
{
  "tool_name": "sslscan",
  "status": "skipped",
  "error_code": "filtered_out",
  "error_message": "Tool filtered out by THANDEV_PIPELINE_TOOLS=httpx,nuclei"
}
```

---

## 4. Verify "sslscan: pending" Fix

**Run a scan and check tool statuses:**
```bash
# After a scan completes, fetch scan details
curl -s "http://localhost:8000/api/scans/<SCAN_ID>" \
  -H "X-Thandev-User-Id: <USER_ID>" \
  -H "X-Thandev-Tenant-Id: <TENANT_ID>" \
  | jq '.tool_statuses[] | select(.tool_name == "sslscan")'
```

**✅ Expected for completed scans:**
- If sslscan was never scheduled: `status: "skipped"` with `error_code: "not_scheduled"`
- If sslscan was scheduled but not started: `status: "skipped"` with `error_code: "not_scheduled"`
- If sslscan ran: `status: "completed"` or `"failed"` or `"timed_out"`

**❌ Should NOT see:**
- `status: "pending"` for completed scans
- Tools stuck in pending forever

---

## 5. Verify Parallelism Check

**Run pro scan test:**
```bash
export RUN_MANUAL_INTEGRATION=1
export THANDEV_PROJECT_ID="<PROJECT_ID>"
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1  # If needed for your plan
pytest test_scan_pipeline.py::test_pro_scan -vv -s
```

**✅ Expected output:**
```
🔄 Parallelism Verification:
   Expected max concurrent tools for pro: 3
   Total tools in scan: 6
   Actual max concurrent tools: 2
   ✅ Max concurrency (2) within limit (3)
```

**If you see:**
```
ℹ️  No tools with timestamps to verify actual concurrency
```
This means the API isn't returning `started_at`/`completed_at` timestamps. Check that `ToolResult` records have these fields populated.

---

## Quick Test Script

Run the automated bypass safety test:
```bash
cd ~/thandev/backend
source venv/bin/activate
python test_bypass_safety.py
```

This tests the bypass logic without needing a running server.

---

## Summary Checklist

- [ ] Production environment blocks bypass (403 error)
- [ ] Dev/test environments allow bypass (scan succeeds)
- [ ] SQLAlchemy available in venv
- [ ] Tool subset filtering creates skipped ToolResult rows
- [ ] No "pending forever" tools in completed scans
- [ ] Parallelism check computes actual max concurrency
- [ ] All regression tests pass: `pytest tests/test_scan_api_regression.py -v`

