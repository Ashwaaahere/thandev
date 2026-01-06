# Tester Quickstart Guide

This guide helps testers quickly set up and test Thandev security scanner.

## Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend)
- Redis (for brain service)
- PostgreSQL or SQLite (SQLite is default for development)

## Quick Setup

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Initialize database
python init_db.py

# Run migrations (required for tool run tracking)
alembic upgrade head

# Seed comprehensive demo data
python scripts/seed_tester_demo.py
```

### 2. Brain Service Setup

```bash
cd services/thandev-brain
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start brain service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4. Start Backend API

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Running Tests

### Unit Tests

```bash
cd backend
source venv/bin/activate
pytest tests/test_brain_status_merge.py -v
pytest tests/test_dalfox_normalization.py -v
```

### Expected Test Output

```
tests/test_brain_status_merge.py::TestBrainSessionResponse::test_parse_completed_session PASSED
tests/test_brain_status_merge.py::TestBrainSessionResponse::test_parse_running_session PASSED
tests/test_dalfox_normalization.py::TestDalfoxOutputNormalization::test_normalize_empty_string PASSED
tests/test_dalfox_normalization.py::TestDalfoxOutputNormalization::test_normalize_empty_dict PASSED
...
```

## Creating Demo Scans

### Using Enhanced Seed Script

```bash
# Run migrations first (required for new tool run tracking fields)
cd backend
source venv/bin/activate
alembic upgrade head

# Create comprehensive demo data (tenant, project, scan with tool runs and findings)
# 
# Option 1: Use --user-id if you know the NextAuth session user ID (recommended)
#   Check browser Network tab → see X-Thandev-User-Id header value
python scripts/seed_tester_demo.py --user-id YOUR_NEXTAUTH_USER_ID

# Option 2: Use --user-email to find user by email
python scripts/seed_tester_demo.py --user-email your-email@example.com

# Option 3: Use first user in database (if no users exist, creates demo-user)
python scripts/seed_tester_demo.py

# Reset and recreate
python scripts/seed_tester_demo.py --reset --user-email your-email@example.com
```

### Demo Data Includes

- **Demo Tenant**: `demo-tenant`
- **Demo Project**: `demo-project` (targets http://testphp.vulnweb.com)
- **Demo Scan**: `demo-scan` (completed scan with tool runs)
  - **Tool Runs**:
    - Dalfox: Success • 1 finding created
    - Nuclei: Success • 0 findings
    - Nmap: Failed (target unreachable)
  - **Findings**:
    - 1 Dalfox XSS finding (medium severity) - visible in UI
  - **Output Files**: Created in `backend/data/jobs/demo-scan/`
    - `dalfox_output.json` (with realistic XSS finding)
    - `nuclei_output.json` (empty array)
    - `nmap_output.json` (empty due to failure)

## Testing Scan Status Transitions

### Expected Status Flow

1. **PENDING** → Scan created, not started
2. **QUEUED** → Scan queued for execution
3. **RUNNING** → Scan in progress
4. **COMPLETED** → All tools finished successfully
5. **STALLED** → Scan running too long without progress (brain unreachable)

### Test Scenarios

#### 1. Normal Scan Completion

```bash
# Create a scan via API
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: demo-user" \
  -H "X-Thandev-Tenant-Id: demo-tenant" \
  -d '{"project_id": "demo-project", "scan_level": "basic"}'

# Check status (should transition: PENDING → QUEUED → RUNNING → COMPLETED)
curl http://localhost:8000/api/scans/{scan_id} \
  -H "X-Thandev-User-Id: demo-user" \
  -H "X-Thandev-Tenant-Id: demo-tenant"
```

#### 2. Dalfox No Findings

When dalfox finds no XSS vulnerabilities, it outputs `[{}]`. This should:
- Be normalized to `[]` at write time
- Create **0 findings** in the database
- Log: `"Dalfox ingestion completed: no findings"`

#### 3. Brain Unreachable

If brain service is down:
- Status source should be `"db"`
- Status reason should be `"brain_unreachable"`
- After threshold (30 min default), scan should be marked `STALLED`

## Testing Dalfox Output Normalization

### Test Cases

1. **Empty output** → Should create 0 findings, file should be `[]`
2. **`[{}]` output** → Should be normalized to `[]`, create 0 findings
3. **Valid XSS finding** → Should create 1 finding, file contains valid JSON array
4. **NDJSON format** → Should parse line-by-line correctly
5. **JSON array format** → Should parse as array correctly

### Manual Test

```bash
# Check dalfox output file (always created, even if empty)
cat backend/data/jobs/{scan_id}/dalfox_output.json

# Should be `[]` if no findings, or valid JSON array/NDJSON with findings
# File path is stored in tool_results.output_path
```

### Verify Tool Run Tracking

```bash
# Check tool results in database
cd backend
source venv/bin/activate
python3 -c "
from app.core.database import SessionLocal
from app.models.finding import ToolResult
db = SessionLocal()
results = db.query(ToolResult).filter(ToolResult.scan_job_id == 'demo-scan').all()
for r in results:
    print(f'{r.tool_name}: status={r.status.value if r.status else None}, parsed={r.parsed_findings_count}, created={r.created_findings_count}, output_path={r.output_path}')
db.close()
"
```

## Status Source and Reason

API response includes:
- `status_source`: `"brain"` or `"db"` (where status came from)
- `status_reason`: Reason for status (e.g., `"stalled_brain_unreachable"`, `"all_tools_done"`)

### Example Response

```json
{
  "id": "scan-123",
  "status": "completed",
  "status_source": "brain",
  "status_reason": null,
  "findings": [...]
}
```

## Common Issues

### Scan Stuck in "Running"

1. Check brain service is running: `curl http://localhost:8001/health`
2. Check scan age: If > 30 minutes, should be marked STALLED
3. Check logs: `backend/logs/app.log` for brain fetch errors

### Dalfox Creates Fake Findings

1. Check output file: Should be `[]` not `[{}]`
2. Check logs: Should see "Normalizing dalfox placeholder output"
3. Verify ingestion logs: Should show `"stored_findings": 0`

### DateTime Errors

All timestamps are now timezone-aware (UTC). If you see `datetime.utcnow()` errors:
- Check imports: Should use `from datetime import datetime, timezone`
- Use `datetime.now(timezone.utc)` instead of `datetime.utcnow()`

## QA Checklist

- [ ] Start scan → Observe status transitions (PENDING → RUNNING → COMPLETED)
- [ ] Dalfox run with no findings → 0 findings in UI
- [ ] Brain down → `status_source="db"`, after threshold → `status="stalled"`
- [ ] Valid XSS finding → Appears in UI with correct severity
- [ ] Scan completion → PDF report generation enabled
- [ ] Status reconciliation → Brain status overrides DB when available

## Logs Location

- Backend: `backend/logs/app.log`
- Brain: `services/thandev-brain/logs/app.log`
- Structured logs include: `scan_id`, `tool_name`, `parsed_items`, `stored_findings`

## Need Help?

- Check logs for structured error messages
- Verify all services are running (backend, brain, redis)
- Check database for scan status: `SELECT id, status, brain_session_id FROM scan_jobs WHERE id = '...'`

