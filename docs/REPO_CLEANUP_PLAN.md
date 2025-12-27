# Thandev Repo Cleanup Plan

Date: 2025-12-26 — Scope: actionable cleanup (no restructuring executed in this pass).

## Deletion / Archival Candidates
- **Legacy/unused code**
  - `backend/legacy/` and `backend/=4.0.0` — archival only; move to `docs/legacy/` or delete after confirming no imports.
  - `backend/app/routers/` (news/performance/security/exploits) — superseded by `app/api/`; audit imports in `app/main.py`, then delete.
  - `backend/models.py` (root) — legacy models; remove once import scan is clean.
  - Celery path (`backend/app/tasks/celery_app.py`, `start_celery.sh`) — unused with Redis runner; delete after confirming `USE_CELERY_SCAN_EXECUTION` stays false.
  - In-memory domain verification (all `frontend/app/api/domains/*`) — not persisted; replace with backend-backed flow or remove.
- **Artifacts/data**
  - Root SQLite/Redis artifacts (`thandev.db*`, `dump.rdb`, `test_output.log`, `TEST_RESULTS_E2E.json`, `test_scan_flow.py`) — delete and ensure `.gitignore` coverage.
  - `backend/data/jobs/*` and `backend/wordlists/*` generated content — keep gitignored; move any sample fixtures to `docs/samples/`.
- **Duplicate docs/PDFs**
  - Consolidate PDFs to `docs/` single-source; remove `docs/exports/pdfs/*` duplicates after re-export.
  - Move historical fix/readme summaries in root to `docs/history/` (retain `CHANGELOG.md` in root).
- **Scripts**
  - One-off scripts in backend root (`cancel_all_scans.py`, `dedupe_references.py`, `verify_*`, `ingest_nvd.py`, `real_data_ingestion.py`) — move to `scripts/archive/` if not part of current flow.

## Refactor Candidates
- **Service size reduction**
  - Split `backend/app/services/scan_orchestrator.py` into orchestration vs notification/report helpers.
  - Split `backend/app/services/tools.py` and ingestion logic by tool family (nuclei, ffuf, nmap, dalfox) to shrink runner/backfill code.
  - Extract runner DB/Redis utilities from `services/thandev-runner/app/tasks.py` into smaller modules for testability.
- **API consistency**
  - Normalize responses (status/metadata) across `/api/scans`, `/api/findings`, `/api/performance`; add pagination envelope consistently.
  - Move any remaining routers from `app/routers` to `app/api`.
- **Config hardening**
  - Centralize env validation (required in prod) and trim unused defaults (e.g., Celery, SQLite fallbacks) into `config.py` with explicit prod requirements.
- **Security**
  - Add SSRF guard utility (private IP blocking) reused by scans and frontend proxies.
  - Add HMAC callback verification for Cloud Run job callbacks (if kept).

## Naming / Consistency Fixes
- Standardize Python snake_case file names and `test_*.py` pattern.
- Ensure headers/auth docs refer to `X-Thandev-User-Id` / `X-Thandev-Tenant-Id` consistently.
- De-duplicate “complete/summary/fix” markdown names by dating them and moving to `docs/history/`.

## Folder Restructuring Suggestions (do not execute yet)
- Root: keep README/CHANGELOG/docker-compose/fly.toml/vercel.json; move historical markdowns to `docs/history/`, legacy code to `docs/legacy/`.
- Backend: enforce single router home (`app/api`), add `app/services/{orchestrator,tools,ingestion,ai}` submodules to break large files; move scripts to `backend/scripts/`.
- Scripts: create `scripts/{setup,verify,deploy,archive}` and migrate scattered shell/python utilities.
- Docs: keep current PDFs in `docs/`, remove `docs/exports/pdfs` after re-export; add `docs/samples/` for example outputs.

## Execution Order
1) **Safe deletes/ignores (0.5 day)**: remove artifacts in root, add gitignore entries, move PDFs to single location.  
2) **Audit & prune (0.5–1 day)**: check imports for `backend/app/routers`, `backend/models.py`, Celery files; drop if unused.  
3) **Domain verification decision (0.5 day)**: either back with backend + DB or delete in-memory frontend routes.  
4) **Refactor prep (1–2 days)**: split orchestration/tools modules and add shared response/SSRF utilities.  
5) **Docs sweep (0.5 day)**: move history markdowns, regenerate PDFs from updated sources.

## Risk Notes
- Removing legacy routers/models is low risk once import scans are clean.  
- Splitting service files requires regression tests around scan creation, runner ingestion, and findings dedup.  
- Domain verification removal affects any UI surfaces that assume persistence—confirm with product before deletion.  
- Consolidating PDFs is safe; keep one tagged export to avoid losing history.

