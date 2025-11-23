# Performance Scan Debugging Guide

## 🔍 Issue: No Logs After Submitting Scan

If you submit a performance scan but don't see any logs in the backend, follow these steps:

## Step 1: Verify Request Reaches Backend

After submitting a scan, you should see a log like:
```
INFO:app.main:POST /api/performance-scan/ - Client: 172.16.18.226
INFO:app.main:POST /api/performance-scan/ - Status: 200 - Time: 0.034s
```

**If you DON'T see this:**
- The request isn't reaching the backend
- Check frontend console for errors
- Verify `NEXT_PUBLIC_API_BASE` is set correctly in Vercel
- Check network tab in browser DevTools

## Step 2: Check for New Logs After Deployment

After the backend redeploys with the new logging, you should see:

1. **When scan is submitted:**
   ```
   INFO:app.routers.performance:Performance scan request received: job_id=..., url=..., device=...
   INFO:app.routers.performance:Performance scan job created in database: ...
   INFO:app.routers.performance:Background task scheduled for performance scan: ...
   ```

2. **When background task starts:**
   ```
   INFO:app.routers.performance:Background task started for performance scan: job_id=...
   INFO:app.routers.performance:Performance scan job status updated to 'running': ...
   INFO:app.routers.performance:Cloud Run configuration: enabled=..., url_set=...
   ```

3. **If Cloud Run is configured:**
   ```
   INFO:app.routers.performance:Using Cloud Run Service for performance scan: ...
   INFO:app.routers.performance:Calling Cloud Run Service: https://.../run for job ...
   INFO:app.routers.performance:Sending POST request to Cloud Run Service: ...
   INFO:app.routers.performance:Cloud Run Service response: status=200, ...
   INFO:app.routers.performance:Started Cloud Run scan for job ..., cloud job ID: ...
   ```

4. **If Cloud Run is NOT configured:**
   ```
   WARNING:app.routers.performance:Cloud Run not configured, falling back to local Lighthouse for job: ...
   WARNING:app.routers.performance:This may cause out-of-memory errors on Fly.io!
   ```

## Step 3: Check Environment Variables

Run this to see if Cloud Run variables are set:

```bash
fly secrets list -a thandev-backend
```

You should see:
- `CLOUD_RUN_ENABLED`
- `CLOUD_RUN_LIGHTHOUSE_URL`

**If they're missing, set them:**
```bash
fly secrets set CLOUD_RUN_LIGHTHOUSE_URL=https://lighthouse-scanner-697855159499.us-central1.run.app -a thandev-backend
fly secrets set CLOUD_RUN_ENABLED=true -a thandev-backend
fly apps restart thandev-backend
```

## Step 4: Check for Errors

Look for error logs:
```bash
fly logs -a thandev-backend | grep -i error
```

Common errors:
- `Cloud Run Service failed to start scan` - Check Cloud Run Service URL
- `Performance scan failed for job` - Check full error message
- `Out of memory` - Cloud Run not configured, falling back to local

## Step 5: Verify Background Task is Running

FastAPI background tasks run in the same process. If you see:
- "Background task scheduled" but NOT "Background task started"
- The background task might be failing silently

Check for exceptions in logs:
```bash
fly logs -a thandev-backend | grep -i "traceback\|exception\|error"
```

## Step 6: Test Direct API Call

Test if the backend endpoint is working:

```bash
# Get your backend URL
BACKEND_URL=$(fly status -a thandev-backend | grep "Hostname" | awk '{print $2}')

# Test the endpoint
curl -X POST "https://${BACKEND_URL}/api/performance-scan/" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "device": "desktop"}'
```

You should get a response like:
```json
{"jobId": "...", "status": "started", "message": "Performance scan initiated"}
```

Then check logs:
```bash
fly logs -a thandev-backend
```

## Step 7: Check Database

Verify the job was created:

```bash
# SSH into the backend (if possible)
fly ssh console -a thandev-backend

# Or check via API
curl "https://${BACKEND_URL}/api/performance-scan/"
```

## Common Issues & Solutions

### Issue: No logs at all after scan submission

**Possible causes:**
1. Request not reaching backend
2. Backend not deployed with new code
3. Logs being filtered

**Solution:**
- Check frontend console for errors
- Verify backend is deployed: `fly status -a thandev-backend`
- Check deployment time matches your latest push
- Try direct API call (Step 6)

### Issue: "Cloud Run not configured" warning

**Solution:**
```bash
fly secrets set CLOUD_RUN_LIGHTHOUSE_URL=<your-url> -a thandev-backend
fly secrets set CLOUD_RUN_ENABLED=true -a thandev-backend
fly apps restart thandev-backend
```

### Issue: "Cloud Run Service failed to start scan"

**Possible causes:**
1. Wrong Cloud Run URL
2. Cloud Run Service not deployed
3. Network/CORS issues

**Solution:**
- Verify Cloud Run Service URL in Google Cloud Console
- Test Cloud Run Service directly:
  ```bash
  curl -X POST "https://lighthouse-scanner-697855159499.us-central1.run.app/run" \
    -H "Content-Type: application/json" \
    -d '{"url": "https://example.com", "device": "desktop"}'
  ```

### Issue: Background task not starting

**Possible causes:**
1. Exception in background task
2. Database connection issue
3. Environment variable issue

**Solution:**
- Check logs for tracebacks
- Verify database connection
- Check all environment variables are set

## Quick Debug Checklist

- [ ] Backend is deployed with latest code
- [ ] Request reaches backend (see POST log)
- [ ] Environment variables are set (`fly secrets list`)
- [ ] Background task starts (see "Background task started" log)
- [ ] Cloud Run configuration is correct (see "Cloud Run configuration" log)
- [ ] No errors in logs (`fly logs | grep -i error`)
- [ ] Job created in database (check via API)

## Next Steps

1. **Wait for backend to redeploy** (should happen automatically from `main` branch)
2. **Submit a new scan** from the frontend
3. **Check logs immediately:**
   ```bash
   fly logs -a thandev-backend --follow
   ```
4. **Look for the new log messages** listed in Step 2
5. **Share the logs** if you still don't see anything

