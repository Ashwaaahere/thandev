# Thandev Runbook

Date: 2025-12-26. Use this as the single source for operating Thandev locally and in prod-like environments. Secrets are not included.

## Prereqs
- Docker and docker-compose, Python 3.11+, Node 18+, Redis, Postgres (or SQLite for dev).
- Env files: `backend/.env`, `frontend/.env.local`, `services/thandev-runner/.env`, `services/thandev-brain/.env`. Set real secrets for prod (no defaults).

## Start Everything Locally (minimal)
1) **Database & Redis**  
   - Easiest: `docker-compose up -d postgres redis` (or ensure local Postgres on 5432, Redis on 6380 per defaults).  
   - If using SQLite for quick dev, set `DATABASE_URL=sqlite:///./thandev.db` in backend & runner.
2) **Backend API**  
   - `cd backend`  
   - `python -m venv .venv && source .venv/bin/activate`  
   - `pip install -r requirements.txt`  
   - `uvicorn app.main:app --reload --port 8000`
3) **Runner** (must share DB/Redis with backend)  
   - `cd services/thandev-runner`  
   - `pip install -r requirements.txt`  
   - `python app/main.py`
4) **Brain (optional but recommended)**  
   - `cd services/thandev-brain`  
   - `pip install -r requirements.txt`  
   - `uvicorn app.main:app --reload --port 8001`
5) **Frontend**  
   - `cd frontend`  
   - `npm install`  
   - `npm run dev` (port 3000; ensure `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`)

## Run a Scan End-to-End (manual)
1) Sign in via frontend (NextAuth GitHub OAuth or dev credentials).  
2) Create project in UI (or POST `/api/projects`).  
3) Kick off scan via UI or `POST /api/scans` with headers `X-Thandev-User-Id`, `X-Thandev-Tenant-Id`.  
4) Watch statuses: `GET /api/scans`, `GET /api/scans/{id}/tools`, findings via `GET /api/findings?project_id=...`.  
5) Download report: `GET /api/scans/{id}/report.pdf`.  
6) Ensure runner logs show tool execution; findings should appear in DB.

## Performance & Security Scan Proxies (Next API)
- Performance: `POST /api/performance-scan` (Next) → backend `/api/performance/`; `GET /api/performance-scan?jobId=...` for status.  
- Security quick scan (legacy Cloud Run path): `POST /api/security-scan` → backend `/api/security-scan/` if enabled.

## Debugging Tips
- Backend: logs in console; health at `/health`, readiness at `/ready`. Check DB/Redis reachability messages on startup.  
- Runner: ensure `REDIS_URL` and `DATABASE_URL` align with backend; watch for “scan job not found” (DB mismatch) and Redis connectivity.  
- Brain: `/health` and `/ready`; check Qdrant/pgvector connectivity if enabled.  
- CORS/auth: ensure `X-Thandev-User-Id`/`X-Thandev-Tenant-Id` headers present; frontend `thandevApi` helper enforces UUIDs.  
- Domain verification: DNS TXT `_thandev-challenge.<domain>` must match token; bypass only with `DOMAIN_VERIFICATION_DISABLED=true` in local/dev.  
- Plan gating: pro/advanced scans need entitlements; set via `/admin` (admins bootstrap from `THANDEV_ADMIN_EMAILS`/`THANDEV_ADMIN_GITHUB_IDS`).  
- Dalfox skip reasons: “skip: no_injection_points” → add target with query params/forms; “rate_limited” → retry later; stdout/stderr previews are visible in scan details.  
- Reports: PDF generation uses ReportLab; failures usually path/permission issues in `backend/data`.  
- Stalled scans: enable `SCAN_RECOVERY_ENABLED=true` in backend to auto-requeue/recover on startup.

## Redeploy / Production Notes
- **Frontend (Vercel)**: build `npm run build`; envs `NEXT_PUBLIC_API_BASE_URL`, `NEXTAUTH_SECRET`, GitHub OAuth creds, `NEXTAUTH_URL`.  
- **Backend (Fly.io or container)**: build from `backend/Dockerfile`; run Alembic migrations (`alembic upgrade head`). Set `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, CORS origins, and Brain flags.  
- **Runner**: deploy alongside backend; same DB/Redis; restrict Redis network.  
- **Brain**: deploy if AI planning/enrichment required; set `RAG_STORE_TYPE` and provider keys.  
- **Cloud Run jobs**: build and deploy from `cloud-run/security-scanner` or `lighthouse-scanner`; ensure callback secrets/allowlists if used.  
- **Migrations**: run once per deploy to Postgres; skip auto-create tables in prod.  
- **Backups**: snapshot Postgres and Redis regularly; avoid storing artifacts in repo.

## Common Troubleshooting Matrix
- Scan stuck at PENDING/QUEUED: runner not connected to Redis or wrong DB; verify envs and stream `scan_step_requests`.  
- Findings empty: tool output not parsed or `MAX_INDIVIDUAL_FINDINGS_PER_SCAN` exceeded; check runner logs and DB.  
- Auth bootstrap failing: ensure backend `/api/auth/bootstrap` reachable and `SELF_SERVICE_SIGNUP_ENABLED` logic matches environment.  
- Domain verification: current flow is frontend-memory only; not persisted—either ignore or implement backend support.  
- Cloud Run callbacks ignored: add shared secret/HMAC and route in backend; ensure public reachability.

## How to Regenerate Docs/PDFs
- Update markdown (`docs/THANDEV_SYSTEM_BIBLE.md`, `docs/REPO_CLEANUP_PLAN.md`, this runbook).  
- Export: `bash docs/export_docs_to_pdf.sh` or `python generate_thandev_pdf.py`. Keep PDFs in `docs/` (drop duplicates under `docs/exports/pdfs`).

## Private Beta Approval Gate (verification checklist)
- Login with a new GitHub account (non-admin): redirected to `/private-beta`
- Call protected API (e.g., `GET /api/projects`): receives 403 with "Private beta" detail
- Login as admin: dashboard and `/admin` stay accessible
- Approve the user via admin UI: after refresh, the user can access dashboard and APIs

## Admin / Superadmin Bootstrap
- Preferred: set `THANDEV_SUPERADMIN_EXTERNAL_IDS="github:<numeric_id>,github:<numeric_id>"` (immutable GitHub IDs)
- One-time seed for new prod: set `THANDEV_SETUP_TOKEN`, then call `POST /api/admin/bootstrap-superadmin` with `Authorization: Bearer <token>` and params `external_provider=github&external_user_id=<id>` while zero admins exist
- Legacy email-based admin is discouraged (GitHub emails can be private); rely on provider:id instead
- Admin UI `/admin` requires `is_admin=true`; superadmins are any IDs in `THANDEV_SUPERADMIN_EXTERNAL_IDS`
