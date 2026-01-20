# Troubleshooting: Wappalyzer and Retire.js Not Showing

## Current Status

✅ **Dependency worker is running**: Logs show "Starting dependency scan worker loop..."
✅ **Redis connection works**: Backend can connect to Redis
✅ **Code is correct**: ToolResult creation code is in place

❌ **No jobs in Redis stream**: `XLEN dependency_scan_jobs` returns 0
❌ **No ToolResult entries**: No wappalyzer/retire entries in database
❌ **No artifacts**: No url_sca artifacts created

## Root Cause

The issue is that **Pro scans are not actually triggering dependency scan jobs**, or the jobs are failing silently.

## Verification Steps

### 1. Check if Pro scans are being created
```bash
# Check recent Pro scans
docker exec thandev-postgres-1 psql -U postgres -d thandev -c "
SELECT id, scan_level, status, created_at 
FROM scan_jobs 
WHERE scan_level = 'pro' 
ORDER BY created_at DESC 
LIMIT 5;
"
```

### 2. Check backend logs when creating Pro scan
```bash
docker compose -f docker-compose.fly-local.yml logs backend --tail 100 -f
# Then create a Pro scan from UI and watch for:
# - "Enqueuing dependency scan job"
# - "Successfully enqueued dependency scan job"
# - Any Redis errors
```

### 3. Check if jobs are in Redis
```bash
docker exec thandev-redis-1 redis-cli XLEN dependency_scan_jobs
docker exec thandev-redis-1 redis-cli XREAD COUNT 5 STREAMS dependency_scan_jobs 0
```

### 4. Check runner logs for dependency jobs
```bash
docker compose -f docker-compose.fly-local.yml logs thandev-runner --tail 100 | grep -i dependency
```

## Expected Flow

1. **User creates Pro scan** → `POST /api/scans/pro`
2. **Backend logs**: "Enqueuing dependency scan job: scan_id=..."
3. **Backend publishes to Redis**: `XADD dependency_scan_jobs ...`
4. **Backend logs**: "Successfully enqueued dependency scan job ... to Redis stream"
5. **Runner logs**: "Received X dependency scan job(s)"
6. **Runner logs**: "Processing dependency scan job: scan_id=..., job_type=url_sca"
7. **Runner executes**: wappalyzer and retire.js
8. **Runner creates ToolResult**: "Created ToolResult entry for wappalyzer"
9. **Runner posts callback**: Artifact stored in database
10. **Frontend shows**: Tools appear in "Tools Executed" section

## Common Issues

### Issue 1: Backend not publishing jobs
**Symptoms**: No "Enqueuing dependency scan job" in logs
**Fix**: Check if Pro scan endpoint is actually calling `enqueue_dependency_scan_job()`

### Issue 2: Redis connection fails
**Symptoms**: "Redis client not available" in logs
**Fix**: Verify REDIS_URL in backend environment

### Issue 3: Jobs published but not consumed
**Symptoms**: Jobs in Redis stream but runner not processing
**Fix**: Check runner logs for dependency worker errors

### Issue 4: Tools not installed
**Symptoms**: "wappalyzer CLI not found" in runner logs
**Fix**: Install tools in runner Dockerfile

## Next Steps

1. **Create a new Pro scan** and monitor logs
2. **Check all three places**:
   - Backend logs (for publishing)
   - Redis stream (for jobs)
   - Runner logs (for processing)
3. **Verify tools are installed** in runner container
4. **Check database** for ToolResult entries after scan completes
