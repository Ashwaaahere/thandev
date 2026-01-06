# Switch to PostgreSQL for Testing

## Current Issue
Your migrations completed, but you're using **SQLite** instead of **PostgreSQL**. To test the bypass with the production environment, you need PostgreSQL.

## Solution: Update DATABASE_URL

### Step 1: Check Current DATABASE_URL

```bash
cd ~/thandev/backend
cat .env | grep DATABASE_URL
# or
echo $DATABASE_URL
```

### Step 2: Update to PostgreSQL

**Option A: Update .env file**
```bash
cd ~/thandev/backend
# Edit .env file and change DATABASE_URL to:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
```

**Option B: Export environment variable**
```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
```

**Note:** Replace `postgres:postgres` with your actual PostgreSQL username and password.

### Step 3: Run Migrations on PostgreSQL

```bash
cd ~/thandev/backend
source venv/bin/activate
alembic upgrade head
```

### Step 4: Restart API Server

```bash
cd ~/thandev/backend
source venv/bin/activate
export ENVIRONMENT=production
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
export BRAIN_SERVICE_ENABLED=false
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev  # If not in .env
uvicorn app.main:app --reload
```

### Step 5: Test Bypass

```bash
curl -s -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: test-user-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -H "X-Thandev-Tenant-Id: test-tenant-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -d '{"project_id":"test-project-0b5ccc58-914f-41af-813d-510eb8aa0b2c","scan_level":"pro"}' | python3 -m json.tool
```

## Quick Check: Which Database Am I Using?

```bash
cd ~/thandev/backend
source venv/bin/activate
python -c "
from app.core.config import settings
print('DATABASE_URL:', settings.DATABASE_URL)
if 'sqlite' in settings.DATABASE_URL.lower():
    print('⚠️  Using SQLite - switch to PostgreSQL for production testing')
elif 'postgresql' in settings.DATABASE_URL.lower():
    print('✅ Using PostgreSQL')
else:
    print('❓ Unknown database type')
"
```

