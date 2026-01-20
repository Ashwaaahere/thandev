# Testing Instructions for Dependency Scanning

## Prerequisites

1. **Database Connection**: Ensure your `DATABASE_URL` environment variable is set correctly
2. **Backend Running**: Start the FastAPI backend server
3. **Runner Service**: Ensure the runner service is running (if testing end-to-end)

## Step 1: Run Migrations

Once your database is configured, run:

```bash
cd backend
source venv/bin/activate  # or activate your virtual environment
alembic upgrade head
```

This will create the following tables:
- `scan_artifacts` - Stores URL-SCA and Repo-SCA results
- `integrations` - GitHub App/OAuth integrations
- `repo_connections` - Links repositories to projects

## Step 2: Verify Migration

Check that the migration was applied:

```bash
alembic current
```

You should see `0034_add_dependency_scanning_tables` as the current revision.

## Step 3: Test Backend Endpoints

### Test PRO Scan Endpoint

```bash
curl -X POST http://localhost:8000/api/scans/pro \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <your-user-id>" \
  -H "X-Thandev-Tenant-Id: <your-tenant-id>" \
  -d '{
    "project_id": "<project-id>",
    "target_url": "https://demo.owasp-juice.shop"
  }'
```

Expected response:
- Status: 201 Created
- Body: `{ "id": "...", "status": "queued", ... }`

### Test Advanced Scan Endpoint (without repo)

```bash
curl -X POST http://localhost:8000/api/scans/advanced \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <your-user-id>" \
  -H "X-Thandev-Tenant-Id: <your-tenant-id>" \
  -d '{
    "project_id": "<project-id>",
    "target_url": "https://demo.owasp-juice.shop"
  }'
```

### Test GitHub Integration Status

```bash
curl http://localhost:8000/api/integrations/github/status \
  -H "X-Thandev-User-Id: <your-user-id>" \
  -H "X-Thandev-Tenant-Id: <your-tenant-id>"
```

Expected response:
- `{ "connected": false, "provider": "github" }` (if not connected)
- `{ "connected": true, "provider": "github", "installation_id": "..." }` (if connected)

### Test Get Scan Artifacts

```bash
curl http://localhost:8000/api/scans/<scan-id>/artifacts \
  -H "X-Thandev-User-Id: <your-user-id>" \
  -H "X-Thandev-Tenant-Id: <your-tenant-id>"
```

Expected response:
- `{ "items": [] }` (if no artifacts yet)
- `{ "items": [{ "id": "...", "type": "url_sca", "payload": {...}, ... }] }` (if artifacts exist)

## Step 4: Test Frontend

1. **Start the frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

2. **Navigate to a scan report page**:
   - Go to `/projects/[projectId]/scans/[scanId]`
   - You should see the new tabs: Overview, Findings, Tech & Dependencies, Repo Dependencies, AI Summary

3. **Test GitHub Integration**:
   - Navigate to a project settings page
   - Look for the GitHub integration component
   - Test connecting a repository

## Step 5: Test Runner Integration

### Test Runner Callback

```bash
# Generate HMAC signature (example)
SECRET="your-runner-callback-secret"
PAYLOAD='{"scan_id":"test-scan-id","artifact_type":"url_sca","payload":{"mode":"url_sca","target":"https://example.com"}}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

curl -X POST http://localhost:8000/api/runner/callback \
  -H "Content-Type: application/json" \
  -H "X-Runner-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

### Test Progress Endpoint

```bash
curl -X POST http://localhost:8000/api/runner/progress \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <RUNNER_API_TOKEN>" \
  -d '{
    "scan_id": "<scan-id>",
    "step": "httpx",
    "status": "running",
    "message": "Fetching target URL..."
  }'
```

## Step 6: Test Brain Explain Endpoint

```bash
curl -X POST http://localhost:8001/api/v1/scans/<scan-id>/explain \
  -H "Content-Type: application/json" \
  -d '{
    "artifact_types": ["url_sca"],
    "org_id": "<org-id>",
    "project_id": "<project-id>"
  }'
```

## Troubleshooting

### Migration Issues

If migrations fail:
1. Check `DATABASE_URL` is set correctly
2. Verify database credentials
3. Ensure database is running and accessible
4. Check Alembic version: `alembic --version`

### Import Errors

If you see import errors:
1. Ensure virtual environment is activated
2. Install dependencies: `pip install -r requirements.txt`
3. Check Python path: `python -c "import sys; print(sys.path)"`

### Endpoint Errors

If endpoints return 403:
- Check user has PRO/ADVANCED plan assigned
- Verify capability checks are working: `check_scan_capability()`

If endpoints return 404:
- Verify project exists and belongs to user/tenant
- Check scan_id is valid

### Frontend Issues

If tabs don't appear:
1. Check browser console for errors
2. Verify artifacts API is returning data
3. Check network tab for API calls

## Validation Checklist

- [ ] Migration runs successfully
- [ ] All models import without errors
- [ ] API routers are registered
- [ ] PRO scan endpoint creates scan
- [ ] Advanced scan endpoint creates scan
- [ ] Artifacts endpoint returns data
- [ ] Frontend tabs appear correctly
- [ ] GitHub integration component loads
- [ ] Runner callback accepts artifacts
- [ ] Brain explain endpoint works

## Next Steps

1. Configure GitHub App credentials (if testing repo scanning)
2. Set up runner service with required tools (wappalyzer, retire.js, osv-scanner)
3. Test end-to-end flow with real URLs and repositories
4. Monitor logs for any errors or warnings
