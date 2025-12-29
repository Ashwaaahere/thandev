# Development Notes

## Shared Project Filtering Logic

Both the dashboard metrics endpoint (`/api/metrics`) and the projects list endpoint (`/api/projects`) use the same filtering logic to ensure consistency.

**Location:** `backend/app/core/project_utils.py`

**Key Functions:**
- `get_verified_projects_query()` - Returns a SQLAlchemy query for verified/allowlisted projects
- `get_verified_projects_count()` - Returns count of verified projects

**Filtering Logic:**
- Always filters by `tenant_id` and `owner_id` (user)
- For non-admin users: Only includes projects with:
  - Domain verification status = VERIFIED, OR
  - Domain is in allowlist (global or tenant-scoped)
- Admins can optionally see all projects (controlled by `include_all_for_admin` parameter)
- Projects without `root_domain` are excluded

**Usage:**
```python
from app.core.project_utils import get_verified_projects_query, get_verified_projects_count

# For counting (metrics)
count = get_verified_projects_count(db, tenant, current_user)

# For listing (projects list)
query = get_verified_projects_query(db, tenant, current_user)
projects = query.all()
```

**Why This Matters:**
- Ensures dashboard "Total Projects" matches projects list count
- Both endpoints use identical filtering logic
- No soft-delete columns exist in Project model, so filtering is based on verification/allowlist status only

---

## Admin Plan Templates

Plan templates are provided via backend API endpoint `/api/admin/plan-templates` which returns a dictionary mapping plan names to their default limits.

**Location:** `backend/app/api/admin.py` - `get_plan_templates()` endpoint

**Plan Names:**
- `free` - Basic plan with minimal limits
- `individual` - Individual plan
- `team` - Team plan with higher limits

**Frontend Usage:**
1. Admin UI fetches plan templates on load
2. When a plan is selected from dropdown, the limits JSON textarea is auto-filled with the template
3. Admin can still manually edit the limits JSON after selecting a plan
4. On save, both `plan_name` and `limits_json` are stored in the entitlements table

**Template Structure:**
```json
{
  "free": {
    "max_projects": 1,
    "max_scans_per_month": 20,
    "max_concurrent_scans": 1,
    "allowed_scan_levels": ["basic"]
  },
  "individual": {
    "max_projects": 5,
    "max_scans_per_month": 200,
    "max_concurrent_scans": 2,
    "allowed_scan_levels": ["basic", "pro"]
  },
  "team": {
    "max_projects": 20,
    "max_scans_per_month": 2000,
    "max_concurrent_scans": 5,
    "allowed_scan_levels": ["basic", "pro", "advanced"]
  }
}
```

---

## Limits Enforcement

Limits are enforced server-side using centralized utilities in `backend/app/core/limits.py`.

**Key Functions:**
- `get_effective_limits()` - Returns merged limits (entitlements override plan limits)
- `check_limit_exceeded()` - Raises HTTPException with structured error if limit exceeded

**Limit Calculation Priority:**
1. User-scoped entitlements (if exists)
2. Tenant-wide entitlements (if exists)
3. Plan limits (fallback)

**Enforced Limits:**
- `max_projects` - Enforced in:
  - `POST /api/projects` - Project creation
  - `POST /api/domain-verifications/start` - Project creation via verification
  - `POST /api/scans` - Project creation via scan

**What Counts as "Active":**
- Only verified/allowlisted projects are counted (same filtering as projects list)
- Uses `get_verified_projects_count()` to ensure consistency
- Domain verifications are tied to projects; when a project is deleted, related verifications are also deleted (cascade)

**Error Response Format:**
```json
{
  "code": "LIMIT_EXCEEDED",
  "message": "Limit exceeded: max_projects (current: 1, limit: 1)",
  "limit_key": "max_projects",
  "current": 1,
  "limit": 1
}
```

**Logging:**
- Limit checks log: tenant_id, limit_key, current count, limit value, and decision
- Logs are available in backend logs for debugging

---

## Project Deletion and Domain Verification

When a project is deleted:
- Related domain verifications are automatically deleted (database cascade)
- This frees up the verification slot for the tenant
- The limit enforcement uses active project count, so deleted projects don't count toward limits

**Database Schema:**
- `projects` table has no soft-delete columns (`deleted_at`, `is_deleted`, etc.)
- Project deletion is hard delete
- `domain_verifications` table has foreign key to `projects` with cascade delete

---

## Frontend Cache Invalidation

After project deletion:
- Projects list should refresh automatically (uses `useEffect` with session dependency)
- Dashboard metrics should be refetched (if using SWR/React Query, call `mutate()` or `invalidateQueries()`)
- Manual refresh button available on dashboard

**Current Implementation:**
- Projects list uses `useEffect` to reload on mount
- No SWR/React Query detected in current implementation
- Dashboard metrics are fetched on component mount
- Consider adding manual refresh or auto-refresh after mutations

