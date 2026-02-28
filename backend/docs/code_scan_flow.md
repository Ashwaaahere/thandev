# Code Scan Data Flow (GitHub Actions → Thandev UI)

This document explains how CI code scan data flows through Thandev, from ingestion to the dashboard UI.

## 1. CI / GitHub Actions → Backend Ingest

1. **GitHub Actions OIDC token**
   - Workflow requests an OIDC token with audience `thandev`.
   - Example step:

     ```bash
     RESP=$(curl -s -X POST "${THANDEV_BASE_URL}/api/code-scans/oidc/exchange/github" \
       -H "Content-Type: application/json" \
       -d "{\"oidc_token\": \"${{ steps.oidc.outputs.id_token }}\"}")
     ```

2. **Exchange endpoint**
   - Endpoint: `POST /api/code-scans/oidc/exchange/github`
   - Module: `backend/app/api/code_scans.py::oidc_exchange`
   - Verification:
     - Calls `verify_oidc_token_and_extract("github", oidc_token)` in `app/security/oidc_providers.py`.
     - Uses GitHub OIDC discovery + JWKS (cached for 10 minutes).
     - Verifies:
       - Signature (RS256, key selected by `kid`).
       - Issuer: `https://token.actions.githubusercontent.com`.
       - `aud` contains `"thandev"` (string or list).
       - `exp`/`nbf`.
     - Extracts `repo_full_name` and other metadata via `_github_claim_extractor`.
   - Allowlist:
     - Looks up `LinkedRepo` row (`linked_repos` table) for `(provider, repo_full_name, is_enabled=True)`.
     - Fails with 403 if repo is not linked in a project.
   - Token minting:
     - Creates a short-lived **ingest token** stored in Redis under key `thandev:code_ingest:<opaque_token>`.
     - Value includes `{ project_id, provider, repo_full_name }`.

3. **Ingest endpoint**
   - Endpoint: `POST /api/code-scans/ingest`
   - Module: `backend/app/api/code_scans.py::ingest`
   - Auth:
     - `Authorization: Bearer <opaque_ingest_token>` required.
     - `_get_ingest_payload` validates token via Redis and checks repo/provider.
   - Request body:
     - Form fields: `repo`, `ref`, `sha`, `run_id`, `workflow`, `actor`, `run_url`.
     - File fields: `semgrep_json`, `gitleaks_json`, `osv_json`, `trivy_json`, `sbom_json`, `sarif_json`.
   - Storage:
     - Table: `code_scans` (`backend/app/models/code_scan.py`).
     - Model: `CodeScan`.
     - Fields populated:
       - `project_id` (from ingest token).
       - `provider`, `repo_full_name`, `ref`, `sha`, `run_id`.
       - `status="completed"`.
       - `summary_json`: high-level sources (e.g. `["semgrep", "gitleaks"]`).
       - `meta_json`: includes `pipeline_run_url`, `workflow`, `actor`, and `artifacts` dict.
         - `artifacts["semgrep"]` / `["gitleaks"]` / `["osv"]` / `["trivy"]` / `["sbom"]` / `["sarif"]`
           contain the raw JSON uploaded from CI.

## 2. Backend API → Listing + Details

1. **List recent scans for a project**
   - Endpoint: `GET /api/code-scans/scans?project_id=...&limit=...`
   - Module: `backend/app/api/code_scans.py::list_code_scans`.
   - Auth:
     - Requires tenant (`require_tenant`) and approved user (`require_approved_user`).
     - Verifies that the project belongs to the current tenant and owner.
   - Returns:

     ```json
     {
       "items": [
         {
           "id": "...",
           "project_id": "...",
           "scan_type": "code",
           "provider": "github",
           "repo_full_name": "owner/repo",
           "ref": "refs/heads/main",
           "sha": "abc123...",
           "run_id": "123456789",
           "status": "completed",
           "summary_json": { "sources": ["semgrep", "gitleaks"] },
           "meta_json": {
             "pipeline_run_url": "https://github.com/owner/repo/actions/runs/...",
             "actor": "octocat",
             "workflow": "Code Scan",
             "artifacts": {
               "semgrep": { ... },
               "gitleaks": { ... }
             }
           },
           "created_at": "...",
           "completed_at": "..."
         }
       ],
       "total": 1
     }
     ```

2. **Fetch single scan details**
   - Endpoint: `GET /api/code-scans/scans/{scan_id}`
   - Module: `backend/app/api/code_scans.py::get_code_scan`.
   - Auth:
     - Same tenant/user/project scoping as list endpoint.
   - Returns a single `CodeScanItem` including `summary_json` and `meta_json` (with embedded `artifacts`).

3. **Debug endpoint (optional)**
   - Endpoint: `GET /api/debug/code-scans?repo=owner/repo&limit=20`
   - Module: `backend/app/main.py::debug_code_scans`.
   - Enabled only when `OIDC_DEBUG=1` (otherwise 404).
   - Returns the last N `code_scans` rows (IDs + basic metadata) for quick inspection.

## 3. Frontend UI → Dashboard / Code Scan

1. **Code Scan landing page**
   - Route: `/dashboard/code-scan`.
   - Component: `frontend/app/dashboard/code-scan/page.tsx`.
   - Behavior:
     - Loads projects via `/api/projects`.
     - Loads linked repos for the selected project via `/api/code-scans/linked-repos?project_id=...`.
     - Loads recent code scans via `/api/code-scans/scans?project_id=...&limit=10`.
     - Renders:
       - CI provider selection (GitHub only for now).
       - Repo link form (link a GitHub repo to the project).
       - **Recent code scans**: each row shows provider, repo, ref, SHA, status.

2. **Recent code scans row**
   - Each row is now **clickable** and links to:
     - `/dashboard/code-scan/{scanId}`
   - Source:
     - Uses `id` from `CodeScanItem` (from `/api/code-scans/scans`).

3. **Code Scan Details page**
   - Route: `/dashboard/code-scan/[scanId]`.
   - Component: `frontend/app/dashboard/code-scan/[scanId]/page.tsx`.
   - Data fetch:
     - Calls `GET /api/code-scans/scans/{scanId}` using `thandevFetchJSON`.
   - UI:
     - Header: repo (`repo_full_name`), provider, ref, SHA, status, created/completed times, and a link to the CI run (`meta_json.pipeline_run_url`) when present.
     - Tabs: `SEMgrep`, `GITLEAKS`, `OSV`, `TRIVY`, `SBOM`, `SARIF`.
       - For the active tab:
         - Computes a simple issue count:
           - Prefer `results.length` or `issues.length`, or array length when the artifact is an array.
         - Shows a JSON viewer (`<pre>` with `JSON.stringify(artifacts[tool], null, 2)`).

## 4. Reports Page (Current Behavior)

- The existing Reports page (`/dashboard/reports`, `ReportsClient`) is driven by traditional HTTP scan jobs and PDF reports (`scan_jobs` + `pdf_reports`), not `code_scans`.
- Code scan runs currently:
  - Are **not** part of this PDF reports pipeline.
  - Do **not** create `Report` records.
- As a result, code scans:
  - Appear in **Dashboard → Code Scan** (recent list + details).
  - Do **not** appear under **Dashboard → Reports** unless a future bridge is implemented to create/report on `code_scans`.

In summary: GitHub Actions sends an OIDC token and scan artifacts to `/api/code-scans/oidc/exchange/github` and `/api/code-scans/ingest`, which writes `code_scans` rows (including raw artifacts). The UI reads these via `/api/code-scans/scans` and `/api/code-scans/scans/{scan_id}` to show recent runs and per-run details on the Code Scan dashboard, while legacy PDF reports remain separate.

## 5. Ingest robustness (workflow / backend)

- **Gitleaks and SARIF**  
  Many Gitleaks GitHub Actions output `results.sarif` by default, not `gitleaks.json`. The backend accepts both:
  - If you upload `gitleaks_json`, it is stored as the `gitleaks` artifact.
  - If you upload only `sarif_json` (e.g. the SARIF from Gitleaks), the backend also exposes it as the `gitleaks` artifact so the Code Scan details UI can show it under the Gitleaks tab.

- **SBOM filename**  
  The ingest API expects the SBOM file as the form field **`sbom_json`**. The filename on disk in CI can be anything (e.g. `EFTT-code-scan.cyclonedx.json`). In your workflow, send it with:
  `-F "sbom_json=@path/to/your-file.cyclonedx.json"`.

- **Avoid curl exit code 26 (file not found)**  
  Curl returns exit code 26 when a file passed to `-F` does not exist. To avoid failing the whole ingest when a tool did not run or produced no file:
  1. **Verify artifacts exist** before calling curl: e.g. in a step, check each file and only add `-F "semgrep_json=@..."` (and similarly for other tools) if the file exists.
  2. Alternatively, create empty JSON files for missing artifacts (e.g. `echo '{}' > gitleaks.json`) and upload those so every expected form field is present and curl does not see a missing file.

