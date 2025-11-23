# Database Table Fix - `performance_scan_jobs` Missing

## 🔴 Problem

The backend is failing with:
```
psycopg2.errors.UndefinedTable: relation "performance_scan_jobs" does not exist
```

## 🔍 Root Cause

1. **`init_db.py` had wrong import**: It was importing `from models import Base` instead of `from app.models import Base`
2. **Migrations not being run**: The Dockerfile wasn't running Alembic migrations on startup
3. **Table not created**: The `performance_scan_jobs` table is defined in migration `0003_add_indexes_and_performance_scans.py` but wasn't being applied

## ✅ Fix Applied

### 1. Fixed `init_db.py`
- Changed import from `from models import Base` to `from app.models import Base`
- Added explicit imports for all models (`ThreatItem`, `ScanJob`, `PerformanceScanJob`)
- Added logging to show which tables are created
- Added error handling if `DATABASE_URL` is missing

### 2. Updated `Dockerfile`
- Added `alembic upgrade head` to run migrations before starting the server
- Command now: `python init_db.py && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`

## 📋 What This Does

1. **`init_db.py`**: Creates all tables defined in SQLAlchemy models using `Base.metadata.create_all()`
2. **`alembic upgrade head`**: Applies all pending migrations, including:
   - `0001_init.py` - Creates `threat_item` table
   - `0002_add_scan_jobs_table.py` - Creates `scan_jobs` table
   - `0003_add_indexes_and_performance_scans.py` - Creates `performance_scan_jobs` table and indexes

## 🚀 Next Steps

1. **Redeploy backend on Fly.io:**
   ```bash
   cd backend
   fly deploy
   ```

2. **Verify tables are created:**
   - Check Fly.io logs: `fly logs -a thandev-backend`
   - Look for: "Database tables created successfully!"
   - Look for: "Tables created: threat_item, scan_jobs, performance_scan_jobs"

3. **Test performance scan:**
   - Try initiating a performance scan from the frontend
   - Should no longer get "relation does not exist" error

## 🔍 Verification

After deployment, you can verify the table exists by:

```bash
# Connect to Fly.io PostgreSQL (if you have access)
# Or check backend logs for successful table creation
fly logs -a thandev-backend | grep -i "table\|migration\|alembic"
```

---

**Status:** Fixed - Ready for deployment
**Date:** 2025-01-27

