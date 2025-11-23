# Backend Scan Troubleshooting Guide

## 🔴 Current Issue: Backend Returning 500 Error

The frontend is successfully calling the backend, but the backend is returning "Internal Server Error" (500).

---

## 🔍 Possible Causes

### 1. Database Not Initialized
**Symptom:** Backend fails when trying to create scan job record

**Check:**
- Backend logs should show database connection errors
- `init_db.py` may have failed during startup

**Fix:**
- Ensure `psycopg2-binary` is installed (✅ already added to requirements.txt)
- Verify database connection string is correct
- Check if database tables exist

### 2. Database Tables Not Created
**Symptom:** `PerformanceScanJob` table doesn't exist

**Check Backend Logs:**
```
Failed to create performance scan job: (table doesn't exist)
```

**Fix:**
- Run database migrations: `alembic upgrade head`
- Or ensure `init_db.py` creates tables on startup

### 3. Lighthouse Not Available
**Symptom:** Backend fails when trying to run Lighthouse scan

**Check:**
- Dockerfile installs Lighthouse: `npm install -g lighthouse` ✅
- But Lighthouse might not be in PATH during runtime

**Fix:**
- Verify Lighthouse is installed in Docker container
- Check if `lighthouse` command is available

### 4. Database Connection Issue
**Symptom:** Cannot connect to PostgreSQL database

**Check:**
- `DATABASE_URL` environment variable is set correctly
- Database is accessible from Fly.io
- PostgreSQL is running

---

## 🔧 How to Debug

### 1. Check Backend Logs on Fly.io

```bash
fly logs -a thandev-backend
```

Look for:
- Database connection errors
- Table creation errors
- Lighthouse command errors
- Any exception tracebacks

### 2. Test Backend Health Endpoint

```bash
curl https://thandev-backend.fly.dev/health
```

Should return:
```json
{
  "status": "ok",
  "database": {
    "status": "healthy"
  }
}
```

### 3. Test Performance Scan Endpoint Directly

```bash
curl -X POST https://thandev-backend.fly.dev/api/performance-scan \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "device": "desktop"}'
```

This will show the actual backend error message.

---

## ✅ Expected Backend Response

**Success:**
```json
{
  "jobId": "uuid-here",
  "status": "started",
  "message": "Performance scan initiated"
}
```

**Error:**
```json
{
  "detail": "Error message here"
}
```

---

## 🎯 Quick Fixes

### Fix 1: Ensure Database is Initialized

The backend runs `python init_db.py` on startup. Check if this is succeeding.

**In Dockerfile:**
```dockerfile
CMD ["sh", "-c", "python init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

If `init_db.py` fails, the backend won't start.

### Fix 2: Verify Database Connection

Check Fly.io environment variables:
- `DATABASE_URL` should be set to PostgreSQL connection string
- Format: `postgresql://user:password@host:port/database`

### Fix 3: Check Database Tables

The backend needs these tables:
- `performance_scan_jobs` (for PerformanceScanJob model)
- `scan_jobs` (for ScanJob model)

These should be created by `init_db.py` or Alembic migrations.

---

## 📋 Backend Requirements

The backend needs:
- ✅ PostgreSQL database (connection string in DATABASE_URL)
- ✅ psycopg2-binary (✅ added to requirements.txt)
- ✅ Lighthouse installed (✅ in Dockerfile)
- ✅ Database tables created (via init_db.py or migrations)

---

## 🔍 Next Steps

1. **Check Fly.io Backend Logs:**
   ```bash
   fly logs -a thandev-backend
   ```

2. **Test Backend Health:**
   ```bash
   curl https://thandev-backend.fly.dev/health
   ```

3. **Test Performance Scan Directly:**
   ```bash
   curl -X POST https://thandev-backend.fly.dev/api/performance-scan \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com", "device": "desktop"}'
   ```

4. **Check Environment Variables:**
   - Go to Fly.io dashboard
   - Verify `DATABASE_URL` is set correctly

---

**Last Updated:** 2025-01-27
**Status:** Backend returning 500 - needs investigation

