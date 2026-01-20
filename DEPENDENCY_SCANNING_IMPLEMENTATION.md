# Dependency Scanning Implementation Summary

## ✅ Completed Components

### Backend (FastAPI)
1. **Database Models** (`backend/app/models/`)
   - `ScanArtifact` - Stores URL-SCA and Repo-SCA results
   - `Integration` - GitHub App/OAuth integrations
   - `RepoConnection` - Links repositories to projects
   - Migration: `0034_add_dependency_scanning_tables.py`

2. **Capability Checks** (`backend/app/core/capabilities.py`)
   - `check_capability()` - Validates PRO/ADVANCED plan entitlements
   - `has_capability()` - Boolean check without exceptions

3. **API Endpoints** (`backend/app/api/`)
   - `POST /api/scans/pro` - PRO dependency scan (URL-SCA only)
   - `POST /api/scans/advanced` - ADVANCED dependency scan (URL-SCA + optional Repo-SCA)
   - `GET /api/scans/{id}/artifacts` - Get scan artifacts
   - `POST /api/runner/callback` - Runner callback with HMAC verification

4. **GitHub Integration** (`backend/app/api/integrations.py`)
   - `GET /api/integrations/github/status` - Check integration status
   - `POST /api/integrations/github/install-callback` - Handle app installation
   - `GET /api/integrations/github/repos` - List available repositories
   - `POST /api/projects/{id}/repos/connect` - Connect repo to project
   - `GET /api/projects/{id}/repos` - List project repo connections
   - `POST /api/projects/{id}/repos/{id}/disable` - Disable repo connection

### Runner (Python)
1. **Dependency Scanner Module** (`services/thandev-runner/app/dependency_scanner.py`)
   - `run_url_sca_job()` - URL-based dependency scanning
     - HTTP probe with httpx
     - Technology detection with Wappalyzer
     - Client-side JS scanning with retire.js
   - `run_repo_sca_job()` - Repository-based dependency scanning
     - GitHub App token retrieval
     - Repository ZIP download
     - OSV-Scanner execution

2. **Dockerfile Updates** (`services/thandev-runner/Dockerfile`)
   - Node.js 20.x installation
   - wappalyzer-cli and retire.js via npm
   - osv-scanner binary installation

### Brain Service
1. **Explain Endpoint** (`services/thandev-brain/app/api/v1.py`)
   - `POST /api/v1/scans/{scan_id}/explain` - AI explanation of artifacts
   - Fetches artifacts from backend
   - Generates structured explanation using OpenAI
   - Fallback explanation if OpenAI unavailable

### Frontend Components
1. **TechDependenciesPanel** (`frontend/components/Scans/TechDependenciesPanel.tsx`)
   - Displays URL-SCA results
   - Shows fingerprint, technologies, client dependencies, vulnerabilities

2. **RepoDependenciesPanel** (`frontend/components/Scans/RepoDependenciesPanel.tsx`)
   - Displays Repo-SCA results
   - Filters by severity and ecosystem
   - Shows packages and vulnerabilities

3. **AISummaryPanel** (`frontend/components/Scans/AISummaryPanel.tsx`)
   - Fetches AI explanation from brain service
   - Displays summary, key points, actions, limitations

## 🔧 Remaining Tasks

### Frontend Integration
1. **Update Scan Report Page** (`frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`)
   - Add tab navigation (Overview, Findings, Tech & Dependencies, Repo Dependencies, AI Summary)
   - Fetch artifacts when dependency tabs are active
   - Conditionally render tab content

2. **Create Scan Creation Pages**
   - Pro scan page: `/app/projects/[projectId]/scans/pro/page.tsx`
   - Advanced scan page: `/app/projects/[projectId]/scans/advanced/page.tsx`
   - Include GitHub integration UI

3. **GitHub Integration Component** (`frontend/components/Integrations/IntegrationConnectGitHub.tsx`)
   - Handle GitHub App installation flow
   - List available repositories
   - Connect repository to project

### Backend Enhancements
1. **GitHub Installation Token Endpoint**
   - `GET /api/integrations/github/installation-token?installation_id=...`
   - Returns short-lived installation token for runner

2. **Progress Endpoint**
   - `POST /api/runner/progress` - Accept progress updates from runner
   - Broadcast to websocket for real-time UI updates

3. **Runner Job Queue Integration**
   - Update `dependency_scanner.py` service to properly enqueue jobs
   - Consider using Redis streams or HTTP endpoint

## 📝 Testing Instructions

### 1. Run Migrations
```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

### 2. Test PRO Scan
```bash
curl -X POST http://localhost:8000/api/scans/pro \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <user-id>" \
  -H "X-Thandev-Tenant-Id: <tenant-id>" \
  -d '{
    "project_id": "<project-id>",
    "target_url": "https://demo.owasp-juice.shop"
  }'
```

### 3. Test Advanced Scan (with repo)
```bash
# First, connect a repository
curl -X POST http://localhost:8000/api/projects/<project-id>/repos/connect \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <user-id>" \
  -H "X-Thandev-Tenant-Id: <tenant-id>" \
  -d '{
    "provider_repo_id": "123456",
    "full_name": "org/repo"
  }'

# Then start advanced scan
curl -X POST http://localhost:8000/api/scans/advanced \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <user-id>" \
  -H "X-Thandev-Tenant-Id: <tenant-id>" \
  -d '{
    "project_id": "<project-id>",
    "target_url": "https://demo.owasp-juice.shop",
    "repo_connection_id": "<repo-connection-id>"
  }'
```

### 4. Get Artifacts
```bash
curl http://localhost:8000/api/scans/<scan-id>/artifacts \
  -H "X-Thandev-User-Id: <user-id>" \
  -H "X-Thandev-Tenant-Id: <tenant-id>"
```

## 🔐 Security Notes

1. **HMAC Verification**: Runner callback uses `RUNNER_CALLBACK_SECRET` for HMAC-SHA256 signatures
2. **Token Storage**: GitHub installation tokens are NOT stored; fetched on-demand
3. **Repo Allowlist**: Advanced scans only accept `repo_connection_id`, never raw repo URLs
4. **Plan Enforcement**: PRO plan required for URL-SCA, ADVANCED plan required for Repo-SCA

## 📦 Environment Variables

### Backend
- `RUNNER_CALLBACK_SECRET` - Secret for HMAC verification
- `RUNNER_URL` - Runner service URL (default: http://localhost:8002)
- `BACKEND_URL` - Backend URL for callbacks

### Runner
- `BACKEND_URL` - Backend API URL
- `RUNNER_CALLBACK_SECRET` - Secret for HMAC signatures

### Brain
- `CORE_BACKEND_URL` - Backend URL for fetching artifacts
- `OPENAI_API_KEY` - OpenAI API key for explanations

## 🚀 Next Steps

1. Complete frontend tab integration in scan report page
2. Create Pro/Advanced scan creation pages
3. Implement GitHub integration UI component
4. Add progress endpoint and websocket broadcasting
5. Test end-to-end with real repositories
6. Add error handling and retry logic
7. Document API endpoints in OpenAPI schema
