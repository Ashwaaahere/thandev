# Security Scanner Cloud Run Refactor - Complete

## Summary

Successfully refactored the security scanner to use **Cloud Run Jobs exclusively**. All local execution of `nuclei` and `nmap` has been removed from the FastAPI backend.

## Changes Made

### 1. Backend (`backend/app/routers/security.py`)

#### Removed:
- ✅ All `subprocess.run(["nuclei", ...])` calls
- ✅ All `subprocess.run(["nmap", ...])` calls
- ✅ All local scan functions:
  - `run_local_scan_sync()`
  - `run_local_scan()`
  - `run_nuclei_scan()` / `run_nuclei_scan_sync()`
  - `run_nmap_scan()` / `run_port_scan_sync()`
  - `run_ssl_scan()` / `run_ssl_scan_sync()`
  - `run_ffuf_scan()` / `run_ffuf_scan_sync()`
  - `run_nikto_scan()` / `run_nikto_scan_sync()`
  - `run_header_scan()`
  - `get_severity_breakdown()`

#### Updated:
- ✅ Cloud Run Job trigger now uses new environment variables:
  - `TARGET_URL` (was `URL`)
  - `SCAN_ID` (was `JOB_ID`)
  - `CALLBACK_URL` (unchanged)
  - `GCS_BUCKET` (new)
  - `SCAN_TIER` (was `TIER`)
  - `CALLBACK_SECRET` (unchanged)

- ✅ Removed all fallback to local scanning
- ✅ Backend now **requires** Cloud Run Jobs (no local execution)

#### Added:
- ✅ Updated `/api/security-scan/callback/{job_id}` endpoint:
  - Validates `scanId` in request
  - Handles `status` field (`done` or `error`)
  - Processes `summary` JSON
  - Extracts `artifactsPrefix` and builds GCS URLs
  - Updates database with results and artifact URLs

### 2. Cloud Run Job (`cloud-run/security-scanner/`)

#### Updated `scanner.py`:
- ✅ New `run_scan_with_gcs()` method:
  1. Reads env vars: `TARGET_URL`, `SCAN_ID`, `CALLBACK_URL`, `GCS_BUCKET`, `SCAN_TIER`
  2. Executes `nuclei`:
     ```bash
     nuclei -u "$TARGET_URL" -severity low,medium,high,critical \
            -silent -json -o nuclei-output.json
     ```
  3. Executes `nmap`:
     ```bash
     nmap -sV -Pn --top-ports 100 "$TARGET_URL" -oX nmap-output.xml
     ```
  4. Parses results (JSON from nuclei, XML from nmap)
  5. Uploads to GCS:
     - `gs://$GCS_BUCKET/security/$SCAN_ID/nuclei-output.json`
     - `gs://$GCS_BUCKET/security/$SCAN_ID/nmap-output.xml`
  6. Generates summary JSON:
     - Total findings
     - Severity breakdown
     - Open ports
     - Service details
     - Vulnerabilities
  7. POSTs callback to backend:
     ```json
     {
       "scanId": "...",
       "status": "done",
       "summary": {...},
       "artifactsPrefix": "security/$SCAN_ID/"
     }
     ```

#### Updated `Dockerfile`:
- ✅ Added `google-cloud-storage` Python package
- ✅ Already includes `nuclei` and `nmap` installations

### 3. Environment Variables Required

#### Backend (Fly.io):
- `GCP_PROJECT_ID` - GCP project ID
- `GCP_REGION` - GCP region (default: `us-central1`)
- `BACKEND_URL` - Backend URL for callbacks (required)
- `GCS_BUCKET` - GCS bucket for artifacts (default: `thandev-reports`)
- `CALLBACK_SECRET` - Secret for callback validation (optional)
- `CLOUD_RUN_ENABLED` - Must be `true` (no local fallback)

#### Cloud Run Job:
- `TARGET_URL` - URL to scan
- `SCAN_ID` - Unique scan ID
- `CALLBACK_URL` - Backend callback URL
- `GCS_BUCKET` - GCS bucket name
- `SCAN_TIER` - Scan tier (level0, level1, level2)
- `CALLBACK_SECRET` - Secret for callback (optional)

## Architecture Flow

```
1. User → POST /api/security-scan/
   ↓
2. FastAPI creates ScanJob (status: pending)
   ↓
3. FastAPI triggers Cloud Run Job via gcloud CLI
   ↓
4. Cloud Run Job executes:
   - nuclei scan → nuclei-output.json
   - nmap scan → nmap-output.xml
   ↓
5. Cloud Run Job uploads to GCS:
   - gs://bucket/security/{scan_id}/nuclei-output.json
   - gs://bucket/security/{scan_id}/nmap-output.xml
   ↓
6. Cloud Run Job POSTs callback to FastAPI:
   POST /api/security-scan/callback/{scan_id}
   {
     "scanId": "...",
     "status": "done",
     "summary": {...},
     "artifactsPrefix": "security/{scan_id}/"
   }
   ↓
7. FastAPI updates ScanJob:
   - status: completed
   - summary: JSON
   - artifact_urls: GCS URLs
   ↓
8. User polls GET /api/security-scan/status/{scan_id}
   - Returns status, summary, artifacts
```

## Testing Checklist

- [ ] Test 1: Level 0 Scan
  - Input: `http://itsecgames.com/`
  - Expect: Job triggered → Cloud Run executes → Results in GCS → Callback updates DB → UI shows completed

- [ ] Test 2: Invalid URL
  - Expect: Backend returns 400

- [ ] Test 3: Cloud Run Job error
  - Expect: `/status/{id}` shows error status

## Deployment Notes

1. **Backend**: Deploy to Fly.io with updated environment variables
2. **Cloud Run Job**: Build and deploy the updated container:
   ```bash
   gcloud builds submit --tag gcr.io/$PROJECT_ID/security-scanner
   gcloud run jobs update security-scanner-job \
     --image gcr.io/$PROJECT_ID/security-scanner \
     --region $REGION
   ```
3. **GCS Bucket**: Ensure bucket exists and Cloud Run Job has write permissions

## Files Modified

- `backend/app/routers/security.py` - Removed local execution, updated Cloud Run trigger
- `cloud-run/security-scanner/scanner.py` - Added GCS upload and new env var handling
- `cloud-run/security-scanner/Dockerfile` - Added google-cloud-storage package

## Next Steps

1. Deploy backend changes to Fly.io
2. Build and deploy updated Cloud Run Job container
3. Test with a real URL
4. Monitor logs for any issues
5. Verify GCS uploads are working
6. Verify callbacks are received correctly

