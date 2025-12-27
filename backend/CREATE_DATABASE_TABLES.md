# Create Database Tables

## Problem
PostgreSQL is running, but the database tables don't exist. Error: `relation "tenants" does not exist`

## Solution: Run Database Migrations

### Step 1: Run Migrations

```bash
cd ~/thandev/backend
source venv/bin/activate
alembic upgrade head
```

### Step 2: Verify Tables Were Created

```bash
# Check if tables exist
python -c "
from app.core.database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print('✅ Tables created:', len(tables))
print('Tables:', ', '.join(sorted(tables)))
"
```

### Step 3: Restart API Server

After migrations complete, restart your API server (or it will auto-reload):

```bash
# In Terminal 1 (where uvicorn is running)
# Press Ctrl+C to stop, then restart:
cd ~/thandev/backend
source venv/bin/activate
export ENVIRONMENT=production
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
export BRAIN_SERVICE_ENABLED=false
uvicorn app.main:app --reload
```

### Step 4: Test Bypass Again

```bash
curl -s -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: test-user-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -H "X-Thandev-Tenant-Id: test-tenant-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -d '{"project_id":"test-project-0b5ccc58-914f-41af-813d-510eb8aa0b2c","scan_level":"pro"}' | python3 -m json.tool
```

## Alternative: Use the Migration Script

```bash
cd ~/thandev/backend
source venv/bin/activate
./run_migrations.sh
```

## Expected Result After Migrations

You should see output like:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_init, Initial schema
INFO  [alembic.runtime.migration] Running upgrade 0001_init -> 0002_add_scan_jobs_table, Add scan_jobs table
...
INFO  [alembic.runtime.migration] Running upgrade 0011_add_tool_run_tracking -> 0012_add_tool_result_id_to_findings, Add tool_result_id to findings
```

Then the API should work and you can test the bypass!

