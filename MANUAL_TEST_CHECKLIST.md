# Manual Test Checklist - Scan Levels Feature

This checklist verifies the end-to-end functionality of the new scan levels system.

## Prerequisites

- [ ] Backend server running on `http://localhost:8000`
- [ ] Frontend server running on `http://localhost:3000`
- [ ] Database migrations applied
- [ ] Cloud Run Jobs deployed (optional for local testing)

## Frontend UI Tests

### Scan Level Dropdown
- [ ] Navigate to `/dashboard/scan`
- [ ] Verify "Scan Level" dropdown is present (not "Scan Type")
- [ ] Verify "Scan Priority" dropdown is removed
- [ ] Verify dropdown contains exactly 3 options:
  - [ ] Level 0 — Surface (Quick) - 3-8 minutes
  - [ ] Level 1 — Discovery (Buzz) - 10-25 minutes  
  - [ ] Level 2 — Active (Non-destructive) - 20-45 minutes
- [ ] Verify tooltip appears on hover over info icon
- [ ] Verify scan level description updates when selection changes

### Scan Features Preview
- [ ] Verify features list updates based on selected level:
  - [ ] Level 0: SSL/TLS Analysis, Technology Detection, Port Scanning
  - [ ] Level 1: All Level 0 + Subdomain Enumeration, Directory Discovery
  - [ ] Level 2: All Level 1 + CVE Scanning, HTTP Server Analysis
- [ ] Verify estimated duration updates correctly

## Backend API Tests

### Start Scan Endpoint
- [ ] Test valid tier values (level0, level1, level2)
- [ ] Test invalid tier value returns 400 error
- [ ] Test missing URL returns 400 error
- [ ] Test invalid URL format returns 400 error
- [ ] Test rate limiting (4th concurrent scan returns 429)
- [ ] Verify response includes jobId, tier, estimated_duration

### Status Endpoint
- [ ] Test `/api/security-scan/status/{job_id}` returns scan status
- [ ] Verify response includes tier, url, timestamps
- [ ] Test non-existent job_id returns 404

### Results Endpoint
- [ ] Test `/api/security-scan/results/{job_id}` returns scan results
- [ ] Verify completed scans return summary and artifact_urls
- [ ] Test pending/running scans return 400 error

### List Endpoint
- [ ] Test `/api/security-scan/list?user_id=test` returns user's scans
- [ ] Verify pagination works with limit/offset parameters

## Database Tests

### Scan Jobs Table
- [ ] Verify `scan_jobs` table exists with correct schema
- [ ] Verify new scan creates record with tier, preset_version
- [ ] Verify callback updates status, summary, artifact_urls
- [ ] Verify rate limiting query works correctly

## Cloud Run Integration Tests

### Job Execution (if Cloud Run enabled)
- [ ] Test Level 0 scan triggers `thandev-surface` job
- [ ] Test Level 1 scan triggers `thandev-buzz` job
- [ ] Test Level 2 scan triggers `thandev-active` job
- [ ] Verify environment variables passed correctly
- [ ] Verify callback received with proper format

### Local Scan Fallback
- [ ] Test local scanning when Cloud Run disabled
- [ ] Verify tools executed based on tier
- [ ] Verify results processed correctly

## Report Page Tests

### Report Display
- [ ] Navigate to `/dashboard/scan/report/{job_id}`
- [ ] Verify report loads for completed scans
- [ ] Verify security score visualization
- [ ] Verify severity breakdown charts
- [ ] Verify tools used section
- [ ] Verify vulnerability list with proper formatting

### Report Tabs
- [ ] Test Overview tab shows metrics and tools
- [ ] Test Vulnerabilities tab shows detailed findings
- [ ] Test Artifacts tab shows download links
- [ ] Test Timeline tab shows scan progression

## End-to-End Workflow Test

### Complete Scan Flow
1. [ ] Start Level 0 scan with valid URL
2. [ ] Verify scan appears in status with "running" status
3. [ ] Wait for completion (or mock callback)
4. [ ] Verify status changes to "completed"
5. [ ] Navigate to report page
6. [ ] Verify report displays correctly
7. [ ] Test re-running scan with different level

### Error Handling
1. [ ] Test scan with invalid URL
2. [ ] Test scan with unreachable URL
3. [ ] Test callback with invalid signature
4. [ ] Test database connection failure

## Performance Tests

### Rate Limiting
- [ ] Start 3 concurrent scans (should succeed)
- [ ] Start 4th concurrent scan (should fail with 429)
- [ ] Complete one scan, verify 4th can now start

### Scan Duration
- [ ] Level 0 scan completes in reasonable time
- [ ] Level 1 scan takes longer than Level 0
- [ ] Level 2 scan takes longer than Level 1

## Security Tests

### Input Validation
- [ ] Test SQL injection in URL parameter
- [ ] Test XSS in scan results
- [ ] Test path traversal in job_id

### Authentication
- [ ] Test endpoints without proper auth (if implemented)
- [ ] Test callback signature verification

## Browser Compatibility

- [ ] Test in Chrome
- [ ] Test in Firefox
- [ ] Test in Safari
- [ ] Test in mobile browsers

## Accessibility

- [ ] Test keyboard navigation
- [ ] Test screen reader compatibility
- [ ] Test high contrast mode
- [ ] Test zoom levels

## Test Data Cleanup

- [ ] Clean up test scan records
- [ ] Clean up test artifacts
- [ ] Reset rate limiting counters
- [ ] Clear browser cache

## Sign-off

- [ ] All frontend tests pass
- [ ] All backend tests pass
- [ ] All integration tests pass
- [ ] All security tests pass
- [ ] Performance meets requirements
- [ ] Documentation is complete

**Tester**: _________________  
**Date**: _________________  
**Version**: feature/scan-levels-presets
