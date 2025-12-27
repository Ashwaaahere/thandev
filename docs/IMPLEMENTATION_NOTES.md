## Implementation Notes (current workstream)

- Models of interest:
  - `backend/app/models/project.py`: stores project `target_url`; will add `root_domain` lock.
  - `backend/app/models/scan.py`: `ScanJob`, `ScanLevel`, `ScanStatus`.
  - `backend/app/models/user.py`: user record; will add `is_admin` / `is_approved`.
  - `backend/app/models/tenant.py`: `PlanTier` + basic limits (legacy).
  - `backend/app/models/finding.py`: `ToolResult` holds status, error_code, stdout/stderr previews.
- Core utilities:
  - `backend/app/core/tenant_utils.py`: header validation, user/tenant creation; candidate to plug admin bootstrap.
  - `backend/app/core/plans.py`: static plan limits; will be superseded by entitlements.
- API entrypoints:
  - `backend/app/api/projects.py`: project create/list; hook to set `root_domain`.
  - `backend/app/api/scans.py`: scan creation/queueing; enforcement hook for domain verification + plan gating + quotas.
- Reports:
  - `backend/app/services/pdf_reports.py`: totals/severity aggregation to fix.
- Runner:
  - `services/thandev-runner/app/tasks.py`: tool ingestion/execution; dalfox handling lives here.
- Tests:
  - `backend/tests/conftest.py`: SQLite fixtures and auth header helper.

Hook preference for enforcement:
- Centralize domain verification + plan/quota checks inside scan creation dependency in `backend/app/api/scans.py`, reused by scan-create endpoints.

