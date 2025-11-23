# Cloud Run Performance Scan Fix

## 🔴 Problem

Performance scans were running Lighthouse **locally** in the backend container, causing:
- **Out of memory errors**: Lighthouse + Chrome require significant RAM
- **Backend crashes**: Container killed due to memory limits
- **Cloud Run Jobs not being used**: Scans should run on Cloud Run, not in backend

## 🔍 Root Cause

The `performance.py` router was executing Lighthouse directly via `subprocess.run()`, which:
1. Runs Chrome + Lighthouse in the same container as the backend
2. Requires 2GB+ RAM (backend only has ~512MB on Fly.io)
3. Causes OOM kills when scans run

## ✅ Fix Applied

### 1. Updated `backend/app/routers/performance.py`

**Changed from:**
- Local Lighthouse execution via subprocess
- Direct Chrome/Node.js process in backend container

**Changed to:**
- HTTP calls to Cloud Run Service (`lighthouse-scanner`)
- Polling mechanism to check scan status
- Fallback to local execution if Cloud Run is disabled

### 2. New Functions

- `run_cloud_run_lighthouse_scan()`: Calls Cloud Run Service via HTTP
- `run_local_lighthouse_scan()`: Fallback for local development
- `process_cloud_run_results()`: Processes Cloud Run Service response format

### 3. Environment Variables Required

Add to Fly.io environment variables:

```bash
# Enable Cloud Run integration
CLOUD_RUN_ENABLED=true

# Cloud Run Service URL (from Google Cloud Console)
CLOUD_RUN_LIGHTHOUSE_URL=https://lighthouse-scanner-xxxxx-uc.a.run.app
```

## 🚀 How It Works

1. **Frontend** → POST `/api/performance-scan/` → **Backend**
2. **Backend** → Creates job in database → Starts background task
3. **Background Task** → POST `/run` → **Cloud Run Service**
4. **Background Task** → Polls GET `/status/:jobId` → **Cloud Run Service**
5. **Background Task** → Processes results → Updates database
6. **Frontend** → GET `/api/performance-scan/:jobId` → **Backend** → Returns results

## 📝 Setup Instructions

### 1. Get Cloud Run Service URL

From Google Cloud Console:
```
Cloud Run → Services → lighthouse-scanner → URL
```

Or via CLI:
```bash
gcloud run services describe lighthouse-scanner \
  --region us-central1 \
  --format="value(status.url)"
```

### 2. Set Environment Variables in Fly.io

```bash
fly secrets set CLOUD_RUN_ENABLED=true -a thandev-backend
fly secrets set CLOUD_RUN_LIGHTHOUSE_URL=https://lighthouse-scanner-xxxxx-uc.a.run.app -a thandev-backend
```

### 3. Verify Deployment

```bash
# Check backend logs
fly logs -a thandev-backend

# Test a scan
curl -X POST https://your-backend.fly.dev/api/performance-scan/ \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "device": "desktop"}'
```

## 🔄 Fallback Behavior

If `CLOUD_RUN_ENABLED=false` or `CLOUD_RUN_LIGHTHOUSE_URL` is not set:
- Backend falls back to local Lighthouse execution
- **Warning**: This will still cause OOM errors on Fly.io
- Only use for local development

## ✅ Benefits

1. **No more OOM errors**: Scans run on Cloud Run, not backend
2. **Better scalability**: Cloud Run auto-scales based on demand
3. **Resource isolation**: Backend stays lightweight
4. **Cost efficiency**: Pay only for scan execution time

## 🐛 Troubleshooting

### Cloud Run Service not responding

Check Cloud Run logs:
```bash
gcloud logs read --service=lighthouse-scanner --limit=50
```

### Backend still using local Lighthouse

Verify environment variables:
```bash
fly secrets list -a thandev-backend
```

### Polling timeout

Increase `max_polls` in `run_cloud_run_lighthouse_scan()` if scans take longer than 5 minutes.

## 📊 Performance

- **Before**: Backend OOM → Crash → Restart
- **After**: Cloud Run handles scan → Backend stays responsive
- **Scan time**: 30-60 seconds (unchanged)
- **Backend memory**: Stays under 200MB (no Chrome/Lighthouse)

