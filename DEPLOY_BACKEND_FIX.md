# Deploy Backend Fix for Security Scan

## Issue
The security scan is failing with error: `parameter 'request' must be an instance of starlette.requests.Request`

## Fix Applied
✅ Fixed the slowapi rate limiter parameter name issue in `backend/app/routers/security.py`

## Deploy the Fix

### Option 1: Deploy via Fly.io CLI (Recommended)

```bash
# Make sure you're in the project root
cd /home/avi/Downloads/thandev-github-starter/thandev

# Deploy the backend
fly deploy -a thandev-backend
```

### Option 2: Deploy via Git Push (if auto-deploy is enabled)

```bash
# Push the changes
git push origin main

# Fly.io will auto-deploy if configured
```

### Option 3: Manual Deploy

```bash
# Build and deploy
cd backend
fly deploy -a thandev-backend
```

## Verify Deployment

After deployment, check the logs:

```bash
fly logs -a thandev-backend
```

You should see:
- No more `parameter 'request' must be an instance` errors
- Security scan requests should succeed

## Test the Fix

1. Go to your dashboard: `https://thandev.vercel.app/dashboard/scan`
2. Enter a URL (e.g., `http://itsecgames.com/`)
3. Select a scan level
4. Click "Start Security Scan"
5. It should work now! ✅

## What Was Fixed

- Changed `http_request: Request` → `request: Request` (required by slowapi)
- Changed `request: SecurityScanRequest` → `scan_request: SecurityScanRequest` (to avoid conflict)
- Updated all references throughout the function

The fix is committed and ready to deploy!

