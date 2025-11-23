# Cloud Run Secret Troubleshooting

## Issue: Secret is set but not being read

If you've set `CLOUD_RUN_LIGHTHOUSE_URL` but logs still show `url_set=False`, try these steps:

## Step 1: Verify Secret Name is Exact

The code reads: `os.getenv("CLOUD_RUN_LIGHTHOUSE_URL", "")`

**Secret name must be EXACTLY:** `CLOUD_RUN_LIGHTHOUSE_URL`

Check for:
- ✅ Correct: `CLOUD_RUN_LIGHTHOUSE_URL`
- ❌ Wrong: `CLOUD_RUN_LIGHTHOUSE_SERVICE_URL`
- ❌ Wrong: `CLOUD_RUN_LIGHTHOUSE_URL_` (trailing underscore)
- ❌ Wrong: `CLOUD_RUN_LIGHTHOUSE` (missing _URL)

## Step 2: Verify Secret is Set

```bash
fly secrets list -a thandev-backend
```

You should see:
```
CLOUD_RUN_ENABLED
CLOUD_RUN_LIGHTHOUSE_URL
```

If you don't see `CLOUD_RUN_LIGHTHOUSE_URL`, set it:
```bash
fly secrets set CLOUD_RUN_LIGHTHOUSE_URL=https://lighthouse-scanner-697855159499.us-central1.run.app -a thandev-backend
```

## Step 3: Restart the App

**Secrets only take effect after restart!**

```bash
fly apps restart thandev-backend
```

Wait 30-60 seconds for the app to fully restart.

## Step 4: Check Logs After Restart

After restart, check the new detailed logs:
```bash
fly logs -a thandev-backend --follow
```

Submit a scan and look for:
```
Cloud Run environment variables: {'CLOUD_RUN_ENABLED': 'true', 'CLOUD_RUN_LIGHTHOUSE_URL': 'https://...'}
```

This will show you exactly what environment variables the app sees.

## Step 5: If Still Not Working

### Option A: Unset and Reset the Secret

```bash
# Remove the secret
fly secrets unset CLOUD_RUN_LIGHTHOUSE_URL -a thandev-backend

# Set it again
fly secrets set CLOUD_RUN_LIGHTHOUSE_URL=https://lighthouse-scanner-697855159499.us-central1.run.app -a thandev-backend

# Restart
fly apps restart thandev-backend
```

### Option B: Redeploy the App

Sometimes a full redeploy helps:
```bash
fly deploy -a thandev-backend
```

### Option C: Check for Typos in URL

Make sure the URL is correct:
- Starts with `https://`
- No trailing slash
- Correct project ID and region

Get the correct URL from Google Cloud Console:
1. Go to Cloud Run → Services
2. Click on `lighthouse-scanner`
3. Copy the URL shown

## Step 6: Verify in Code

The code checks:
```python
cloud_run_url = os.getenv("CLOUD_RUN_LIGHTHOUSE_URL", "")
```

If this returns empty string, the environment variable is not set.

## Common Issues

### Issue: Secret set but app not restarted
**Solution:** Always restart after setting secrets:
```bash
fly apps restart thandev-backend
```

### Issue: Secret name typo
**Solution:** Double-check the exact name: `CLOUD_RUN_LIGHTHOUSE_URL`

### Issue: Secret set in wrong app
**Solution:** Make sure you're using `-a thandev-backend` flag

### Issue: URL has trailing slash
**Solution:** Remove trailing slash from URL

## Debug Commands

```bash
# List all secrets
fly secrets list -a thandev-backend

# Check app status
fly status -a thandev-backend

# View recent logs
fly logs -a thandev-backend

# SSH into app (if possible)
fly ssh console -a thandev-backend
# Then inside: env | grep CLOUD_RUN
```

## Expected Log Output After Fix

After setting the secret correctly and restarting, you should see:

```
INFO:app.routers.performance:Cloud Run environment variables: {'CLOUD_RUN_ENABLED': 'true', 'CLOUD_RUN_LIGHTHOUSE_URL': 'https://lighthouse-scanner-697855159499.us-central1.run.app'}
INFO:app.routers.performance:Cloud Run configuration: enabled=True, url_set=True, url_length=67, url_value=https://lighthouse-scanner-697855159499.us-central1.run.app
INFO:app.routers.performance:Using Cloud Run Service for performance scan: ...
```

Instead of:
```
INFO:app.routers.performance:Cloud Run configuration: enabled=True, url_set=False, url_length=0, url_value=EMPTY
WARNING:app.routers.performance:Cloud Run not configured, falling back to local Lighthouse
```

