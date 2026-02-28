# Code Scan Flow (GitHub Actions → Thandev UI)

End-to-end flow for viewing code scan results in the Thandev dashboard.

## Flow summary

1. **GitHub Actions** runs your code scan workflow (Semgrep, Gitleaks, OSV, Trivy, SBOM, etc.).
2. **OIDC exchange**: Workflow calls `POST /api/code-scans/oidc/exchange/github` with the GitHub OIDC token; backend verifies it and returns a short-lived **ingest token** (repo must be linked to a project in Thandev).
3. **Ingest**: Workflow calls `POST /api/code-scans/ingest` with `Authorization: Bearer <ingest_token>` and uploads artifacts as form file fields (`semgrep_json`, `gitleaks_json`, `osv_json`, `trivy_json`, `sbom_json`, `sarif_json`).
4. **DB**: Backend creates a `code_scans` row with `summary_json` and `meta_json.artifacts` (raw JSON per tool).
5. **List**: UI fetches `GET /api/code-scans/scans?project_id=...` and shows recent code scans; each row is clickable.
6. **Detail**: Clicking a row opens `/dashboard/code-scan/[scanId]`, which fetches `GET /api/code-scans/scans/{scan_id}` and shows scan metadata plus tabs (Semgrep, Gitleaks, OSV, Trivy, SBOM, SARIF) with raw JSON viewers.

Detailed API and implementation notes: see `backend/docs/code_scan_flow.md`.

## Ingest robustness

- **Gitleaks**: If the workflow only uploads SARIF (e.g. Gitleaks action outputs `results.sarif`), send it as `sarif_json`; the backend also exposes it under the Gitleaks tab.
- **SBOM**: Send the SBOM file as the form field **`sbom_json`**; the local filename can be anything (e.g. `myrepo.cyclonedx.json`).
- **Curl exit 26**: Uploading a non-existent file causes curl to fail. In CI, either (1) only add `-F` for files that exist, or (2) create empty `{}` files for missing artifacts and upload those so ingest always receives all keys.
