# Exact Commands to Start Database and Test Bypass

## Step 1: Check if PostgreSQL is Running

```bash
# Check if PostgreSQL service is running
sudo systemctl status postgresql

# OR check if Docker container is running
docker ps | grep postgres

# OR check if port 5432 is listening
netstat -tuln | grep 5432
# or
ss -tuln | grep 5432
```

## Step 2: Start PostgreSQL

### Option A: If using systemd (Ubuntu/Debian)
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql  # Auto-start on boot
```

### Option B: If using Docker
```bash
# Check for docker-compose.yml
cd ~/thandev
docker-compose up -d postgres

# OR if you have a standalone postgres container
docker start <postgres-container-name>
```

### Option C: If using Docker directly
```bash
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=thandev \
  -p 5432:5432 \
  postgres:latest
```

## Step 3: Verify Database Connection

```bash
cd ~/thandev/backend
source venv/bin/activate
python -c "from app.core.database import engine; conn = engine.connect(); print('✅ Database connected'); conn.close()"
```

If this fails, check your `DATABASE_URL` in `.env` or environment variables.

## Step 4: Start API Server

**Terminal 1:**
```bash
cd ~/thandev/backend
source venv/bin/activate
export ENVIRONMENT=production
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
export BRAIN_SERVICE_ENABLED=false
uvicorn app.main:app --reload
```

Wait for: `INFO: Application startup complete.`

## Step 5: Test Bypass

**Terminal 2:**
```bash
curl -s -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: test-user-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -H "X-Thandev-Tenant-Id: test-tenant-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -d '{"project_id":"test-project-0b5ccc58-914f-41af-813d-510eb8aa0b2c","scan_level":"pro"}' | python3 -m json.tool
```

## Expected Results

### With `ENVIRONMENT=production`:
```json
{
    "detail": "Your plan does not allow 'pro' scans. Allowed levels: basic."
}
```
**HTTP Status:** 403 Forbidden  
**✅ This means bypass is SAFE (correctly blocked)**

### With `ENVIRONMENT=dev`:
```json
{
    "id": "...",
    "status": "queued",
    ...
}
```
**HTTP Status:** 201 Created  
**✅ This means bypass works (allowed in dev)**

## Troubleshooting

### If PostgreSQL still won't start:
```bash
# Check PostgreSQL logs
sudo journalctl -u postgresql -n 50

# OR for Docker
docker logs <postgres-container-name>
```

### If connection still fails:
```bash
# Check DATABASE_URL
cd ~/thandev/backend
cat .env | grep DATABASE_URL
# Should be something like: postgresql://user:pass@localhost:5432/dbname
```

### Quick Test Script
```bash
#!/bin/bash
# Quick test if database is accessible
cd ~/thandev/backend
source venv/bin/activate
python << EOF
from app.core.database import SessionLocal
try:
    db = SessionLocal()
    db.execute("SELECT 1")
    print("✅ Database is accessible")
    db.close()
except Exception as e:
    print(f"❌ Database error: {e}")
EOF
```

