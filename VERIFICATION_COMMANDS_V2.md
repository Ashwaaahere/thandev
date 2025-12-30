# Verification Commands for Production Fixes (Both Columns Strategy)

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

## Quick Verification

### 1. Check Both Time Columns Exist
```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
python3 << 'EOF'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'scan_jobs'
        AND column_name IN ('finished_at', 'completed_at')
        ORDER BY column_name
    """))
    columns = [row[0] for row in result.fetchall()]
    print('Time columns in scan_jobs:')
    for col in columns:
        print(f'  ✓ {col}')
    if 'finished_at' not in columns:
        print('  ✗ finished_at missing!')
    if 'completed_at' not in columns:
        print('  ✗ completed_at missing!')
    if len(columns) == 2:
        print('\n✓ Both columns exist')
EOF
```

### 2. Check Alembic Version
```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
alembic current
```

Expected: `0024_ensure_time_columns (head)`

Or check directly in DB:
```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
python3 << 'EOF'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text('SELECT version_num FROM alembic_version LIMIT 1'))
    version = result.scalar()
    print(f'Current alembic_version: {version}')
EOF
```

### 3. Check All scan_jobs Columns
```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
python3 << 'EOF'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'scan_jobs'
        ORDER BY ordinal_position
    """))
    columns = result.fetchall()
    print('scan_jobs columns:')
    for col in columns:
        print(f'  - {col[0]}: {col[1]}')
    col_names = {col[0] for col in columns}
    required = ['id', 'project_id', 'scan_level', 'status', 'finished_at', 'completed_at']
    missing = [col for col in required if col not in col_names]
    if missing:
        print(f'\n✗ Missing required columns: {missing}')
    else:
        print('\n✓ All required columns present')
EOF
```

### 4. Test Schema-Check Endpoint
```bash
curl -H "X-Thandev-User-Id: <admin_user_id>" \
     -H "X-Thandev-Tenant-Id: <admin_tenant_id>" \
     https://thandev-backend.fly.dev/api/admin/db/schema-check | jq
```

Expected response should show:
- `alembic_version`: "0024_ensure_time_columns" (or later)
- `scan_jobs_columns` includes both `finished_at` and `completed_at`
- `missing_columns`: [] (empty)

### 5. Test Scan Creation (Should NOT 500)
```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-Thandev-User-Id: <user_id>" \
     -H "X-Thandev-Tenant-Id: <tenant_id>" \
     -d '{"target_url": "https://example.com", "scan_level": "basic"}' \
     https://thandev-backend.fly.dev/api/scans/quick
```

Expected outcomes:
- **201 Created**: Scan created successfully ✅
- **403 Forbidden**: Plan limit exceeded (expected, not an error) ✅
- **500 Internal Server Error**: Should NOT happen anymore ❌

### 6. Check App Startup Logs
```bash
fly logs -a thandev-backend | grep -i "alembic\|database\|schema\|version\|scan_jobs" | tail -40
```

Expected log messages:
```
Alembic DB version: 0024_ensure_time_columns
Alembic expected head: 0024_ensure_time_columns
scan_jobs table columns (X total): ... finished_at, completed_at, ...
All critical scan_jobs columns are present
```

Should NOT see:
- "column scan_jobs.finished_at does not exist"
- "column scan_jobs.completed_at does not exist"
- "Missing critical columns" warning
- "Alembic version mismatch!" warning (unless there's a real mismatch)

## Manual Migration (if needed)

If migrations didn't run automatically:

```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade 0023_fix_scan_jobs_columns -> 0024_ensure_time_columns, ensure scan_jobs has both finished_at and completed_at columns
Added column: finished_at (if missing)
Added column: completed_at (if missing)
Synced finished_at and completed_at columns
```

## Verify Column Sync

Check that both columns are in sync (have the same values):

```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
python3 << 'EOF'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Check for rows where columns don't match
    result = conn.execute(text("""
        SELECT id, finished_at, completed_at
        FROM scan_jobs
        WHERE (finished_at IS NULL AND completed_at IS NOT NULL)
           OR (finished_at IS NOT NULL AND completed_at IS NULL)
           OR (finished_at != completed_at)
        LIMIT 10
    """))
    mismatches = result.fetchall()
    if mismatches:
        print(f'⚠ Found {len(mismatches)} rows with mismatched time columns:')
        for row in mismatches:
            print(f'  ID: {row[0]}, finished_at: {row[1]}, completed_at: {row[2]}')
    else:
        print('✓ All rows have synced time columns (or both are NULL)')
EOF
```

