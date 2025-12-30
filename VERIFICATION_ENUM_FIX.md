# Verification Commands for Scan Level Enum Fix

After deploying the fixes, run these commands to verify the enum fix works correctly.

## 1. Check Current Enum Values in Postgres

```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
python3 << 'PYEOF'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT enumlabel 
        FROM pg_enum 
        JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
        WHERE pg_type.typname = 'scanlevel'
        ORDER BY enumsortorder
    """))
    values = [row[0] for row in result.fetchall()]
    print('Current scanlevel enum values:')
    for val in values:
        print(f'  - {val}')
    expected = {'basic', 'pro', 'advanced'}
    missing = expected - set(values)
    if missing:
        print(f'\n⚠ Missing values: {missing}')
    else:
        print('\n✓ All canonical values present')
PYEOF
```

Expected output:
```
Current scanlevel enum values:
  - basic
  - pro
  - advanced

✓ All canonical values present
```

## 2. Check Existing Data in scan_jobs

```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
python3 << 'PYEOF'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT DISTINCT scan_level::text, COUNT(*) as count
        FROM scan_jobs
        WHERE scan_level IS NOT NULL
        GROUP BY scan_level
        ORDER BY scan_level
    """))
    rows = result.fetchall()
    print('Current scan_level values in scan_jobs:')
    for val, count in rows:
        print(f'  - {val}: {count} rows')
    # Check for uppercase variants
    uppercase_variants = [val for val, _ in rows if val.isupper() or val[0].isupper()]
    if uppercase_variants:
        print(f'\n⚠ Found uppercase variants: {uppercase_variants}')
        print('   Migration should have backfilled these. Check migration logs.')
    else:
        print('\n✓ All values are lowercase canonical')
PYEOF
```

## 3. Test Scan Creation from UI

1. Go to the Security Scanner page
2. Enter a valid URL
3. Select a scan level (Basic/Pro/Advanced)
4. Click "Start Scan"

**Expected outcomes:**
- ✅ Scan starts successfully (no 500 error)
- ✅ If there's an error, UI shows a readable message (not "[object Object]")
- ✅ Error messages are specific (e.g., "Invalid scan_level: 'BASIC'. Must be one of: basic, pro, advanced")

## 4. Test Scan Creation via API

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <your_user_id>" \
  -H "X-Thandev-Tenant-Id: <your_tenant_id>" \
  https://thandev-backend.fly.dev/api/scans/quick \
  -d '{
    "target_url": "https://example.com",
    "scan_level": "basic"
  }'
```

**Expected responses:**

✅ **Success (201):**
```json
{
  "project_id": "...",
  "scan_id": "..."
}
```

✅ **Invalid scan_level (400):**
```json
{
  "detail": {
    "code": "INVALID_SCAN_LEVEL",
    "message": "Invalid scan_level: 'BASIC'. Must be one of: basic, pro, advanced",
    "allowed": ["basic", "pro", "advanced"],
    "received": "BASIC"
  }
}
```

❌ **Should NOT see:**
- 500 error with "invalid input value for enum scanlevel"
- "[object Object]" in UI
- Generic "Failed to fetch" without details

## 5. Test Case-Insensitive Input

The backend should accept case-insensitive input and normalize it:

```bash
# Test uppercase
curl -X POST ... -d '{"target_url": "https://example.com", "scan_level": "BASIC"}'

# Test mixed case
curl -X POST ... -d '{"target_url": "https://example.com", "scan_level": "Pro"}'

# Test lowercase (canonical)
curl -X POST ... -d '{"target_url": "https://example.com", "scan_level": "basic"}'
```

All three should work and create a scan with `scan_level='basic'` in the database.

## 6. Check Migration Status

```bash
fly ssh console -a thandev-backend
# Then inside the shell:
cd /app
alembic current
```

Expected: `0025_fix_scanlevel_enum (head)` or later

## 7. Check App Logs for Errors

```bash
fly logs -a thandev-backend | grep -i "scan_level\|scanlevel\|enum\|invalid" | tail -20
```

Should NOT see:
- `invalid input value for enum scanlevel`
- `psycopg2.errors.InvalidTextRepresentation`

