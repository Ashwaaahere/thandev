# Verification Commands for Production Fixes

After deploying the fixes, run these commands to verify everything works.

## Prerequisites

1. Make sure you're logged into Fly.io:
   ```bash
   fly auth whoami
   ```

2. Get your admin token (if needed for API calls):
   ```bash
   # You'll need to authenticate as an admin user via the frontend
   # or use fly ssh to run commands directly on the backend
   ```

## A) Verify Migration Status

### Check Current Alembic Version
```bash
fly ssh console -a thandev-backend -C "cd /app && alembic current"
```

Expected output after migration:
```
0024_rename_finished_at (head)
```

### Check Alembic Version Directly in DB
```bash
fly ssh console -a thandev-backend -C "python3 -c \"
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text('SELECT version_num FROM alembic_version LIMIT 1'))
    version = result.scalar()
    print(f'Current alembic_version: {version}')
\""
```

### Check scan_jobs Table Columns
```bash
fly ssh console -a thandev-backend -C "python3 -c \"
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = \\'public\\' AND table_name = \\'scan_jobs\\'
        ORDER BY ordinal_position
    '''))
    columns = result.fetchall()
    print('scan_jobs columns:')
    for col in columns:
        print(f'  - {col[0]}: {col[1]}')
    # Check specifically for completed_at vs finished_at
    col_names = {col[0] for col in columns}
    if 'completed_at' in col_names:
        print('\\n✓ completed_at column exists')
    elif 'finished_at' in col_names:
        print('\\n⚠ finished_at exists (migration 0024 not run yet)')
    else:
        print('\\n✗ Neither completed_at nor finished_at found!')
\""
```

Expected: Should show `completed_at` after migration 0024 runs.

## B) Verify Schema-Check Endpoint

### Test Schema-Check Endpoint
```bash
# Get your admin token from the frontend session, then:
curl -H "X-Thandev-User-Id: <admin_user_id>" \
     -H "X-Thandev-Tenant-Id: <admin_tenant_id>" \
     https://thandev-backend.fly.dev/api/v1/admin/db/schema-check | jq
```

Or from within the backend:
```bash
fly ssh console -a thandev-backend -C "python3 -c \"
import os
import requests
import json
# You'll need to set admin user/tenant IDs
headers = {
    'X-Thandev-User-Id': '<admin_user_id>',
    'X-Thandev-Tenant-Id': '<admin_tenant_id>'
}
resp = requests.get('http://localhost:8000/api/admin/db/schema-check', headers=headers)
print(json.dumps(resp.json(), indent=2))
\""
```

Expected response:
```json
{
  "alembic_version": "0024_rename_finished_at",
  "expected_head": "0025_stamp_version",
  "scan_jobs_columns": [...],
  "missing_columns": []
}
```

### Test Alembic Versions Endpoint
```bash
curl -H "X-Thandev-User-Id: <admin_user_id>" \
     -H "X-Thandev-Tenant-Id: <admin_tenant_id>" \
     https://thandev-backend.fly.dev/api/admin/db/alembic-versions | jq
```

Expected: Should show one alembic_version table in 'public' schema with version_num.

## C) Verify Scan Creation Works

### Test Quick Scan Endpoint
```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-Thandev-User-Id: <user_id>" \
     -H "X-Thandev-Tenant-Id: <tenant_id>" \
     -d '{"target_url": "https://example.com", "scan_level": "basic"}' \
     https://thandev-backend.fly.dev/api/scans/quick
```

Expected outcomes:
- **Success (201)**: Scan created successfully
- **403 Forbidden**: Plan limit exceeded (expected, not a 500 error)
- **500 Internal Server Error**: Should NOT happen anymore (indicates migration didn't run)

If you get a 500, check the error message:
```bash
# Check backend logs
fly logs -a thandev-backend | grep -i "completed_at\|finished_at\|schema\|migration" | tail -20
```

## D) Verify App Startup Logs

### Check Startup Logs
```bash
fly logs -a thandev-backend | grep -i "alembic\|database\|schema\|version" | tail -30
```

Expected log messages:
```
Alembic DB version: 0024_rename_finished_at
Alembic expected head: 0025_stamp_version
Database connection: postgresql://user:***@host:port/dbname
scan_jobs table columns (X total): id, project_id, scan_level, status, ..., completed_at, ...
All critical columns present in scan_jobs table
```

Should NOT see:
- "Alembic version mismatch!" warning
- "Missing critical columns" warning
- "column scan_jobs.completed_at does not exist" error

## E) Run Migrations Manually (if needed)

If migrations didn't run automatically:

```bash
fly ssh console -a thandev-backend -C "cd /app && alembic upgrade head"
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 0022_add_scan_jobs_columns -> 0023_fix_scan_jobs_columns, fix_scan_jobs_missing_columns
INFO  [alembic.runtime.migration] Running upgrade 0023_fix_scan_jobs_columns -> 0024_rename_finished_at, rename finished_at to completed_at in scan_jobs
INFO  [alembic.runtime.migration] Running upgrade 0024_rename_finished_at -> 0025_stamp_version, stamp alembic version if schema matches head
```

## F) Quick Health Check Script

Run this all-in-one check:

```bash
fly ssh console -a thandev-backend -C "python3 << 'EOF'
import os
from sqlalchemy import create_engine, text

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print('✗ DATABASE_URL not found')
    exit(1)

engine = create_engine(db_url)

print('=== Alembic Version ===')
with engine.connect() as conn:
    result = conn.execute(text('SELECT version_num FROM alembic_version LIMIT 1'))
    version = result.scalar()
    print(f'Current: {version}')
    print(f'Expected: 0025_stamp_version (or 0024_rename_finished_at)')
    if version in ['0024_rename_finished_at', '0025_stamp_version']:
        print('✓ Version looks good')
    else:
        print(f'⚠ Version mismatch - may need to run migrations')

print('\\n=== scan_jobs Columns ===')
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'scan_jobs'
        ORDER BY column_name
    '''))
    columns = {row[0] for row in result.fetchall()}
    
    required = ['completed_at', 'scan_level', 'stack_info', 'celery_task_id', 'error_message']
    missing = [col for col in required if col not in columns]
    
    if 'completed_at' in columns:
        print('✓ completed_at exists')
    elif 'finished_at' in columns:
        print('⚠ finished_at exists (migration 0024 not run)')
    else:
        print('✗ Neither completed_at nor finished_at found!')
    
    if missing:
        print(f'✗ Missing required columns: {missing}')
    else:
        print('✓ All required columns present')
EOF
"
```

Expected output:
```
=== Alembic Version ===
Current: 0024_rename_finished_at
Expected: 0025_stamp_version (or 0024_rename_finished_at)
✓ Version looks good

=== scan_jobs Columns ===
✓ completed_at exists
✓ All required columns present
```

