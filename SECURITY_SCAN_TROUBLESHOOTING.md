# Security Scan Troubleshooting Guide

This guide helps you diagnose and fix security scan failures after deployment.

## Common Issues and Solutions

### Issue 1: "gcloud CLI not installed" Error

**Symptoms:**
- Error message: "gcloud CLI not installed"
- Scan fails immediately after starting

**Cause:**
The backend is trying to execute a Cloud Run Job but `gcloud` CLI is not available in the deployment environment.

**Solutions:**

#### Option A: Use Local Scanning (Recommended for Development)
Set environment variable to disable Cloud Run:
```bash
# For Fly.io
fly secrets set CLOUD_RUN_ENABLED=false -a thandev-backend

# For local development
export CLOUD_RUN_ENABLED=false
```

Then restart the backend:
```bash
fly apps restart thandev-backend
```

#### Option B: Install gcloud CLI in Backend Container
If you need Cloud Run scanning, add `gcloud` CLI to your backend Dockerfile:
```dockerfile
# Add to backend/Dockerfile
RUN curl https://sdk.cloud.google.com | bash
ENV PATH $PATH:/root/google-cloud-sdk/bin
```

#### Option C: Use Cloud Run API Directly
Instead of using `gcloud` CLI, use the Cloud Run REST API or Python client library.

---

### Issue 2: "GCP_PROJECT_ID environment variable is required" Error

**Symptoms:**
- Error message: "GCP_PROJECT_ID environment variable is required"
- Scan fails when trying to use Cloud Run

**Cause:**
Required environment variables for Cloud Run are not set.

**Solution:**
Set the required environment variables:

```bash
# For Fly.io
fly secrets set GCP_PROJECT_ID=your-project-id -a thandev-backend
fly secrets set GCP_REGION=us-central1 -a thandev-backend
fly secrets set BACKEND_URL=https://your-backend-url.com -a thandev-backend
fly secrets set CALLBACK_SECRET=your-secret-key -a thandev-backend

# Restart after setting secrets
fly apps restart thandev-backend
```

**Required Variables:**
- `GCP_PROJECT_ID` - Your Google Cloud Project ID
- `GCP_REGION` - Region where Cloud Run Job is deployed (default: us-central1)
- `BACKEND_URL` - Your backend URL for callbacks (must be publicly accessible)
- `CALLBACK_SECRET` - Secret key for callback authentication

---

### Issue 3: "Cloud Run Job failed" Error

**Symptoms:**
- Error message: "Cloud Run Job failed: ..."
- Scan starts but fails during execution

**Possible Causes:**

1. **Cloud Run Job not deployed**
   ```bash
   # Check if job exists
   gcloud run jobs list --region=us-central1
   
   # If not, deploy it
   cd cloud-run
   ./deploy-security-scanner.sh YOUR_PROJECT_ID us-central1
   ```

2. **Incorrect job name**
   - Check the job name in `backend/app/routers/security.py`:
     ```python
     TIER_TO_JOB = {
         "level0": "security-scanner-job",
         "level1": "security-scanner-job", 
         "level2": "security-scanner-job"
     }
     ```
   - Make sure it matches your deployed Cloud Run Job name

3. **Insufficient permissions**
   - The backend needs permission to execute Cloud Run Jobs
   - For Fly.io, ensure service account has `run.jobs.execute` permission

4. **Callback URL not accessible**
   - The Cloud Run Job must be able to reach your backend callback URL
   - Ensure `BACKEND_URL` is publicly accessible
   - Check firewall rules and network configuration

---

### Issue 4: Scan Times Out or Hangs

**Symptoms:**
- Scan starts but never completes
- Status remains "running" indefinitely

**Solutions:**

1. **Check Cloud Run Job logs:**
   ```bash
   gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=security-scanner-job" --limit=50
   ```

2. **Check backend logs:**
   ```bash
   fly logs -a thandev-backend
   ```

3. **Increase timeout:**
   - Cloud Run Job timeout is set to 30 minutes (1800s)
   - Backend timeout is also 30 minutes
   - Adjust if needed in the code

---

### Issue 5: "Local scan failed" Error

**Symptoms:**
- Error when `CLOUD_RUN_ENABLED=false`
- Local scanning tools not available

**Cause:**
Security scanning tools (nuclei, nmap, sslscan, etc.) are not installed in the backend container.

**Solutions:**

1. **Enable fallback (if Cloud Run is configured):**
   ```bash
   fly secrets set FALLBACK_TO_LOCAL_SCAN=true -a thandev-backend
   fly apps restart thandev-backend
   ```

2. **Install tools in backend container:**
   Add to `backend/Dockerfile`:
   ```dockerfile
   # Install security scanning tools
   RUN apt-get update && apt-get install -y \
       nuclei \
       nmap \
       sslscan \
       nikto \
       && rm -rf /var/lib/apt/lists/*
   ```

---

## Diagnostic Steps

### Step 1: Check Environment Variables

```bash
# For Fly.io
fly secrets list -a thandev-backend

# Check logs for diagnostic info
fly logs -a thandev-backend | grep "Cloud Run configuration"
```

You should see:
```
Cloud Run configuration: project=your-project, region=us-central1, job=security-scanner-job, callback_url=https://...
```

### Step 2: Test Cloud Run Job Directly

```bash
# Execute job manually
gcloud run jobs execute security-scanner-job \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --update-env-vars URL=https://example.com,TIER=level1,JOB_ID=test-123,CALLBACK_URL=https://your-backend.com/api/security-scan/callback/test-123
```

### Step 3: Check Backend Health

```bash
# Check if backend is running
curl https://your-backend-url.com/health

# Check scan endpoint
curl -X POST https://your-backend-url.com/api/security-scan/ \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "tier": "level1", "user_id": "test"}'
```

### Step 4: Review Error Messages

Check the scan job status:
```bash
# Get scan status
curl https://your-backend-url.com/api/security-scan/status/JOB_ID

# Check database for error details
# The error message will be in the scan_job.summary field
```

---

## Quick Fixes

### Fix 1: Disable Cloud Run (Use Local Scanning)

```bash
# Set environment variable
fly secrets set CLOUD_RUN_ENABLED=false -a thandev-backend

# Restart
fly apps restart thandev-backend
```

**Note:** This requires security tools to be installed in the backend container.

### Fix 2: Enable Fallback to Local Scanning

If Cloud Run fails, automatically fall back to local scanning:

```bash
fly secrets set FALLBACK_TO_LOCAL_SCAN=true -a thandev-backend
fly apps restart thandev-backend
```

### Fix 3: Use Mock/Test Mode

For testing, you can modify the code to return mock results instead of running actual scans.

---

## Environment Variables Checklist

Before deploying, ensure these are set:

### Required for Cloud Run Scanning:
- [ ] `CLOUD_RUN_ENABLED=true` (or false to disable)
- [ ] `GCP_PROJECT_ID=your-project-id`
- [ ] `GCP_REGION=us-central1` (or your region)
- [ ] `BACKEND_URL=https://your-backend-url.com`
- [ ] `CALLBACK_SECRET=your-secret-key`

### Optional:
- [ ] `FALLBACK_TO_LOCAL_SCAN=true` (enable fallback if Cloud Run fails)

---

## Testing After Fix

1. **Start a test scan:**
   - Go to dashboard → Security Scan
   - Enter a test URL (e.g., `https://example.com`)
   - Select scan level
   - Click "Start Scan"

2. **Monitor progress:**
   - Check scan status in dashboard
   - Review backend logs: `fly logs -a thandev-backend`
   - Check Cloud Run Job logs if using Cloud Run

3. **Verify results:**
   - Scan should complete within expected time
   - Results should appear in dashboard
   - No error messages in logs

---

## Getting Help

If issues persist:

1. **Check logs:**
   ```bash
   fly logs -a thandev-backend --follow
   ```

2. **Review error details:**
   - Check scan job status endpoint
   - Review error message in scan results

3. **Common log patterns:**
   - `"gcloud CLI not found"` → Use local scanning or install gcloud
   - `"GCP_PROJECT_ID not set"` → Set environment variables
   - `"Cloud Run Job failed"` → Check Cloud Run Job deployment
   - `"Local scan failed"` → Install security tools or use Cloud Run

---

## Best Practices

1. **For Production:**
   - Use Cloud Run Jobs for scanning
   - Ensure all environment variables are set
   - Monitor Cloud Run Job execution
   - Set up alerts for failed scans

2. **For Development:**
   - Use local scanning (`CLOUD_RUN_ENABLED=false`)
   - Install security tools locally
   - Test with small, safe URLs

3. **For Testing:**
   - Use mock mode or test endpoints
   - Verify error handling
   - Test fallback mechanisms

