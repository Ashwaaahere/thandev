# Frontend Migration: Summary Schema Keys

## Status: TODO (Backend emits both canonical and deprecated keys)

## Canonical vs Deprecated Keys

**Canonical keys** (prefer these):
- `findings_count` (replaces `total_findings`)
- `severity_breakdown` (replaces `findings_by_severity`)

**Deprecated aliases** (fallback only):
- `total_findings` (use `findings_count` instead)
- `findings_by_severity` (use `severity_breakdown` instead)

## Current State
- Backend emits both canonical and deprecated keys during migration period
- Frontend currently reads `findings_count` (canonical) and `findings_by_severity` (deprecated - mixed usage)

## Migration Steps

1. **Update TypeScript types** in:
   - `frontend/app/projects/[projectId]/scans/[scanId]/page.tsx` (line 62-69)
   - `frontend/app/projects/[projectId]/scans/page.tsx` (line 51-58)
   - Any other files using `ScanSummary` type

2. **Change all reads to prefer canonical keys with fallback**:
   ```typescript
   // Prefer canonical, fallback to deprecated
   const findingsCount = scan.summary?.findings_count ?? scan.summary?.total_findings ?? 0;
   const severityBreakdown = scan.summary?.severity_breakdown ?? scan.summary?.findings_by_severity ?? {};
   ```

3. **Update all references**:
   - Change `scan.summary.findings_by_severity` to use `severity_breakdown` with fallback
   - Keep `findings_count` (already canonical)

4. **After frontend migration complete**: Remove deprecated keys from backend (Phase 3)

## Files to Update
- `frontend/app/projects/[projectId]/scans/[scanId]/page.tsx` (line 605, 607, 609, 1412)
- `frontend/app/projects/[projectId]/scans/page.tsx` (line 56-57)

