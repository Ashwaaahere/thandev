# Verification Steps for Dependency Scanning Fixes

## Quick Test Commands

### 1. Check Backend Logs
```bash
docker compose -f docker-compose.fly-local.yml logs backend --tail 50 | grep -i "dependency\|artifact\|url_sca"
```

### 2. Check Runner Logs
```bash
docker compose -f docker-compose.fly-local.yml logs thandev-runner --tail 50 | grep -i "dependency\|url_sca\|artifact"
```

### 3. Check Redis Stream
```bash
docker exec thandev-redis-1 redis-cli XREAD COUNT 5 STREAMS dependency_scan_jobs 0
```

### 4. Check Database for Artifacts
```bash
docker exec thandev-postgres-1 psql -U postgres -d thandev -c "SELECT id, scan_id, type, created_at FROM scan_artifacts ORDER BY created_at DESC LIMIT 5;"
```

### 5. Test Artifacts Endpoint
```bash
# Replace <scan-id> with actual scan ID
curl -H "X-Thandev-User-Id: <user-id>" \
     -H "X-Thandev-Tenant-Id: <tenant-id>" \
     http://localhost:8000/api/scans/<scan-id>/artifacts
```

## Expected Behavior

### When Pro Scan is Created:
1. Backend logs: `Enqueuing dependency scan job: scan_id=..., job_type=url_sca`
2. Backend logs: `Successfully enqueued dependency scan job ... to Redis stream`
3. Redis stream: Message appears in `dependency_scan_jobs` stream
4. Runner logs: `Processing dependency scan job: scan_id=..., job_type=url_sca`
5. Runner logs: `Successfully processed dependency scan job ...`
6. Database: Row appears in `scan_artifacts` table with `type='url_sca'`
7. Frontend: Tech & Dependencies tab shows results

### When Tools Are Missing:
1. Runner logs: `wappalyzer CLI not found, skipping technology detection`
2. Runner logs: `retire.js not found, skipping client-side dependency scanning`
3. Runner still posts callback with partial results
4. Artifact created with `meta.tools_missing` array
5. Frontend shows available data (even if limited)

### When Artifacts Endpoint is Called:
1. Returns 200 (not 404)
2. Returns `{"items": [...]}` structure
3. Empty array if no artifacts: `{"items": []}`
4. Contains artifacts if they exist

## Troubleshooting

### Issue: Artifacts endpoint returns 404
**Fix**: Route ordering - ensure `/{scan_id}/artifacts` comes before `/{scan_id}`

### Issue: No jobs in Redis stream
**Fix**: Check backend logs for Redis connection errors

### Issue: Runner not processing jobs
**Fix**: Check runner logs for consumer group creation errors

### Issue: No artifacts in database
**Fix**: Check runner callback logs and HMAC signature verification

### Issue: Frontend shows "No results" even after scan completes
**Fix**: Check browser console for API errors, verify artifacts endpoint returns data
