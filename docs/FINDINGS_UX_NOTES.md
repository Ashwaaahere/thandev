# Findings UX Technical Notes

**Purpose:** Documentation of the current findings UI implementation and planned improvements for making findings more actionable and navigable.

---

## Current Implementation

### Main UI Components

1. **VulnerabilitiesClient** (`frontend/components/Dashboard/VulnerabilitiesClient.tsx`):
   - Main findings list view
   - Table layout with columns: Severity, Title, Tool, Status, Actions
   - Located at: `/vulnerabilities` route (via dashboard)
   - Features:
     - Project filter dropdown
     - Tool filter (all, nuclei, nmap, sslscan, http_headers)
     - Status filter (all, open, acknowledged, resolved, suppressed)
     - Category filter (all, xss, sqli, etc.)
     - Search input (searches title/description)
     - Pagination (20 items per page)

2. **Scan Report Page** (`frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`):
   - Shows findings for a specific scan
   - Card-based layout
   - Displays: title, vuln_type badge, location (method + URL + parameter), severity, status
   - Has remediation section (remediation_summary, remediation_steps)
   - Shows lifecycle info (first_seen_at, last_seen_at, found_count, not_seen_in_latest_scan)

### API Endpoints

**GET /api/findings** (`backend/app/api/findings.py`):
- **Query Parameters:**
  - `severity` (optional): Filter by severity (critical, high, medium, low, info)
  - `status` (optional): Filter by status (open, acknowledged, resolved, suppressed)
  - `tool` (optional): Filter by tool (nuclei, nmap, sslscan, http_headers, httpx, ffuf, dalfox, sqlmap)
  - `project_id` (optional): Filter by project ID
  - `category` (optional): Filter by vulnerability category (xss, sqli, ssrf, etc.)
  - `search` (optional): Search in title, description, CVE ID, CWE ID, URL, path
  - `limit` (default: 20): Pagination limit
  - `offset` (default: 0): Pagination offset

- **Response:**
  ```typescript
  {
    items: FindingListItem[];
    total: number;
  }
  
  type FindingListItem = {
    id: string;
    scan_id: string;
    project_id: string;
    project_name: string;
    target_url: string;
    severity: string;
    status: string;
    title: string;
    description?: string;
    cve_id?: string;
    cwe_id?: string;
    tool?: string;
    categories?: string[];
    url?: string;
    path?: string;
    first_seen: string;  // ISO 8601
    last_seen: string;   // ISO 8601
  }
  ```

**GET /api/scans/{scan_id}/findings** (`backend/app/api/scans.py`):
- Returns findings for a specific scan
- Supports: severity, tool filters
- Pagination: skip, limit

**PATCH /api/findings/{finding_id}/status**:
- Updates finding status (open, acknowledged, resolved, suppressed)

### Current Filtering & Search

**Backend:**
- ✅ Severity filter (single value)
- ✅ Status filter
- ✅ Tool filter
- ✅ Project filter
- ✅ Category filter (searches in raw_data JSON)
- ✅ Search (title, description, CVE, CWE, URL, path)
- ❌ Missing: vuln_type filter
- ❌ Missing: Multiple severity selection (comma-separated)
- ❌ Missing: URL/parameter-specific search

**Frontend:**
- ✅ Severity filter (single select)
- ✅ Status filter (dropdown)
- ✅ Tool filter (dropdown)
- ✅ Category filter (dropdown)
- ✅ Search input
- ✅ Project filter
- ❌ Missing: Multi-select severity
- ❌ Missing: Type filter (vuln_type)

### Current Display Fields

**VulnerabilitiesClient (List View):**
- Severity badge
- Title
- CVE/CWE badges (if present)
- Tool name
- Status badge
- Actions (update status)

**Scan Report Page (Detail View):**
- Title + vuln_type badge
- Location: `METHOD URL?parameter=...`
- Severity
- Status
- Remediation section (summary + steps)
- Lifecycle: first_seen_at, last_seen_at, found_count
- Lifecycle badge: "Not seen in latest scan" or "Present in latest scan"

### Current Limitations

1. **Filtering:**
   - Severity filter only supports single value (not multi-select)
   - No vuln_type filter
   - Search doesn't specifically target URL/parameter fields

2. **Display:**
   - List view doesn't show location (method, URL, parameter)
   - List view doesn't show lifecycle info (first/last seen, not_seen_in_latest_scan)
   - List view doesn't show remediation guidance
   - No clear indication of "still present" vs "not seen in latest scan"

3. **Empty/Error States:**
   - Basic error handling exists but could be improved
   - No specific empty state for filtered results

4. **Navigation:**
   - No direct link from scan detail page to filtered findings list

---

## Planned Improvements

### 1. Backend Enhancements

**New Query Parameters:**
- `vuln_type` (optional): Filter by vuln_type (xss, sqli, csrf, etc.)
- `severity` (enhanced): Support comma-separated values (e.g., `severity=high,critical`)
- `search` (enhanced): Prioritize URL and parameter fields in search

**Response Schema Updates:**
- Add `vuln_type` to FindingListItem
- Add `http_method`, `parameter` to FindingListItem
- Add `first_seen_at`, `last_seen_at` (use lifecycle fields)
- Add `not_seen_in_latest_scan` boolean
- Add `remediation_summary`, `remediation_steps` to FindingListItem
- Add `found_count` to FindingListItem

### 2. Frontend Enhancements

**Filter Bar:**
- Severity multi-select (checkboxes: All, Critical, High, Medium, Low, Info)
- Status dropdown (unchanged)
- Type dropdown (new): All, XSS, SQLi, CSRF, etc. (based on vuln_type)
- Search input (enhanced placeholder: "Filter by URL or path...")

**Per-Finding Display (List View):**
- Title: `[severity badge] [vuln_type]`
- Location: `METHOD URL` + parameter (if present)
- Lifecycle: First seen, Last seen, Lifecycle badge
- Status badge
- Remediation section (collapsible or inline)

**Empty States:**
- No findings: "No issues found by the selected tools and filters."
- No findings (no filters): "No issues found in the latest scans for this project."
- Filtered results empty: "No findings match your current filters." + "Clear filters" button
- Error state: "Could not load findings. Please try again." + Retry button

**Navigation:**
- Add "View findings from this scan" link on scan detail page
- Pre-filter findings list by scan_id (or project_id + latest scan)

---

## Finding Details - Current State

**API Fields Exposed:**
- `GET /api/findings` returns `FindingListItem` with:
  - Basic: id, title, description, severity, status, tool
  - Location: url, http_method, parameter, path
  - Evidence: evidence (short snippet), raw_data_preview (trimmed dict)
  - Lifecycle: first_seen_at, last_seen_at, not_seen_in_latest_scan, found_count
  - Remediation: remediation_summary, remediation_steps
  - Categories: categories (extracted from raw_data)
- `GET /api/findings/{finding_id}` returns `FindingDetailResponse` with:
  - All fields from FindingListItem
  - Full `raw_data` as JSON object (for power users)
- `GET /api/scans/{scan_id}/findings` returns similar structure

**Fields Used in Findings List:**
- Title, severity badge, tool name (demoted to subtle display), status badge
- Location info (method, URL, parameter) shown in table rows
- Lifecycle info (first/last seen, not_seen_in_latest_scan badge)
- Remediation section (summary + steps) in collapsible details

**Modal/Details View:**
- ✅ FindingDetailsDrawer component exists
- ✅ Opens when clicking a finding row
- ✅ Shows all details: location, evidence, remediation, lifecycle, raw JSON
- ✅ Keyboard navigation: Esc to close
- ✅ Status update from drawer

**New Features:**
- Evidence field exposed in API
- raw_data_preview (trimmed) for UI consumption
- Full raw_data available via GET /api/findings/{finding_id}
- Tool names demoted (hidden on mobile, subtle on desktop)

## Implementation Status

- [x] Backend: Add vuln_type filter
- [x] Backend: Support comma-separated severity values
- [x] Backend: Enhance search to prioritize URL/parameter
- [x] Backend: Add lifecycle fields to FindingListItem schema
- [x] Backend: Add remediation fields to FindingListItem schema
- [x] Backend: Add scan_id filter parameter
- [x] Frontend: Add severity multi-select (checkboxes)
- [x] Frontend: Add type filter dropdown (vuln_type)
- [x] Frontend: Enhance per-finding display with location/lifecycle/remediation
- [x] Frontend: Add empty states (no findings, filtered results empty)
- [x] Frontend: Add error states with retry button
- [x] Frontend: Add scan → findings link
- [x] Backend: Add evidence field to FindingListItem schema
- [x] Backend: Add raw_data_preview to FindingListItem schema
- [x] Backend: Add GET /api/findings/{finding_id} endpoint
- [x] Frontend: Create FindingDetailsDrawer component
- [x] Frontend: Wire drawer into findings list
- [x] Frontend: Simplify list cards and demote tool names
- [x] Frontend: Add keyboard navigation (Esc to close)

---

## API Changes Summary

### New/Enhanced Query Parameters

```
GET /api/findings?
  severity=high,critical          # Comma-separated (new) - supports multiple values
  status=open                      # Unchanged
  vuln_type=xss                    # New - filter by normalized vulnerability type
  tool=nuclei                      # Unchanged
  project_id=...                   # Unchanged
  scan_id=...                      # New - filter by specific scan
  category=xss                     # Unchanged (legacy, prefer vuln_type)
  search=/login                    # Enhanced: prioritizes URL/parameter fields
  limit=20                         # Unchanged
  offset=0                         # Unchanged
```

**Implementation Notes:**
- `severity` now accepts comma-separated values (e.g., `severity=high,critical`)
- `search` now prioritizes URL and parameter fields in addition to title/description
- `vuln_type` filters by the normalized `vuln_type` field (more reliable than `category`)
- `scan_id` allows filtering findings from a specific scan

### Enhanced Response Schema

```typescript
type FindingListItem = {
  // Existing fields...
  id: string;
  scan_id: string;
  project_id: string;
  project_name: string;
  target_url: string;
  severity: string;
  status: string;
  title: string;
  description?: string;
  cve_id?: string;
  cwe_id?: string;
  tool?: string;
  categories?: string[];
  url?: string;
  path?: string;
  
  // New fields (all optional for backward compatibility):
  vuln_type?: string;              // e.g., "xss", "sqli"
  http_method?: string;            // e.g., "GET", "POST"
  parameter?: string;              // e.g., "q", "username"
  first_seen_at?: string;          // ISO 8601 (from lifecycle)
  last_seen_at?: string;           // ISO 8601 (from lifecycle)
  not_seen_in_latest_scan?: boolean;
  found_count?: number;
  remediation_summary?: string;
  remediation_steps?: string;      // JSON array or newline-separated
  
  // Legacy fields (for backward compatibility):
  first_seen?: string;             // Alias for first_seen_at
  last_seen?: string;              // Alias for last_seen_at
}
```

**Field Usage:**
- `vuln_type`: Displayed as badge next to title
- `http_method`, `url`, `parameter`: Shown as "METHOD URL?parameter=..." in location section
- `evidence`: Shown in FindingDetailsDrawer "Evidence" section
- `raw_data_preview`: Shown as key/value table in FindingDetailsDrawer
- `first_seen_at`, `last_seen_at`: Displayed in lifecycle section
- `not_seen_in_latest_scan`: Shown as badge ("Not seen in latest scan" or "Present in latest scan")
- `found_count`: Displayed as "Seen in N scans"
- `remediation_summary`, `remediation_steps`: Shown in collapsible "How to fix" section

---

## Current Finding Card Layout

**VulnerabilitiesClient Table View:**
- **Columns:** Severity, Finding, Project, Tool (hidden on mobile), CVSS, Status, Detected, Actions
- **Finding Column Shows:**
  - Title (e.g., "Cross-Site Scripting (XSS)")
  - vuln_type badge (if available)
  - Location: METHOD URL?parameter=... (if available)
  - CVE/CWE badges (if available)
  - Lifecycle info: First seen, Last seen, "Not seen in latest scan" badge
  - Remediation summary (collapsible `<details>` with "How to fix")
- **Tool Column:** Shows tool name (e.g., "dalfox", "httpx", "nmap") - **TO BE REMOVED**
- **Status:** Badge + dropdown for quick status update
- **Actions:** Link to view scan

**FindingDetailsDrawer (Modal/Details View):**
- ✅ Exists and opens on row click
- Shows: Title, location, status, "What was found" (description), "Evidence", "How to fix", lifecycle, CVE/CWE, advanced details (tool + raw JSON)
- ❌ Missing: "Why it matters" section (impact explanation)

## Finding Details Drawer

**Component:** `frontend/components/Dashboard/FindingDetailsDrawer.tsx`

**Features:**
- Slides in from right side when a finding row is clicked
- Shows comprehensive finding details:
  - Header: Severity badge, vuln_type badge, close button
  - Title and location (METHOD URL + parameter)
  - Status badge and lifecycle indicators
  - "What was found" section (description)
  - "Evidence" section (evidence field + raw_data_preview table)
  - "How to fix" section (remediation_summary + steps)
  - "Lifecycle" section (first/last seen, found_count)
  - "References" section (CVE/CWE badges)
  - "Advanced details" collapsible section:
    - Tool name ("Found by: dalfox/nuclei/sqlmap")
    - Full raw_data JSON (collapsible)
- Footer: Project name + status update dropdown
- Keyboard navigation: Esc key closes drawer
- Backdrop click closes drawer

**API Integration:**
- On open, fetches full finding details via `GET /api/findings/{finding_id}`
- Falls back to list item data if fetch fails
- Status updates sync with parent list

**UX Improvements:**
- Tool names removed from primary UI: No longer shown in table columns or card headers
- Tool names only visible in "Technical details" collapsible section in drawer
- List rows are clickable to open drawer
- Status dropdown in list stops propagation to prevent accidental drawer opens

## Location & Remediation – Target Behavior

**WHERE IT WAS FOUND:**
- Should show HTTP method + URL and parameter whenever available
- Must extract location from raw_data if direct fields are missing (via display_location_url fallback)
- Should default to "GET" for method if not specified
- Should show "Location information not available" only when truly no location data exists
- Frontend uses tolerant logic: `method = http_method || "GET"`, `url = url || path || null`

**Common Vuln Types (XSS, SQLi, open ports, insecure HTTP):**
- Should almost never show "Remediation guidance not available..." fallback
- Must have useful "WHY IT MATTERS" explanations (derived from vuln_type if impact_summary missing)
- Must have concrete "HOW TO FIX IT" steps (from remediation_summary/remediation_steps or default_remediation_steps)
- Backend populates remediation_summary and remediation_steps during ingestion via get_remediation_hint()
- Added remediation hints for: xss, sqli, open_port, open_service, insecure_http

**Card Robustness:**
- Cards handle missing fields gracefully
- Use tolerant logic: prefer available data, fall back to raw_data parsing (backend), then show helpful messages
- Never crash or show empty sections when data is partially available
- Frontend derives WHY/HOW from vuln_type when backend fields are missing

**Backfill Scripts:**
- `backend/scripts/backfill_finding_locations.py`: Extracts url, http_method, parameter from raw_data for existing findings
- Run with `--dry-run` to preview changes before committing

---

## Target Finding Card Layout

**Goal:** Every finding card must have 4 clear sections that are understandable to both non-security people and developers.

**Card Structure (4 Required Sections):**

1. **WHERE IT WAS FOUND:**
   - Label: "Where it was found"
   - Content: HTTP METHOD + URL
   - Parameter: <name> (if present)
   - **Must be shown for ALL relevant vulns** (XSS, SQLi, SSRF, etc.), not just httpx/nmap findings
   - If URL/method/parameter are missing, show "Location information not available"

2. **WHAT WE FOUND:**
   - Label: "What we found"
   - Content: Description from backend (tool-generated text)
   - If description is long (>200 chars), show first 200 chars + "Click for more" hint
   - This explains what the scanner detected

3. **WHY IT MATTERS:**
   - Label: "Why it matters"
   - Content: Simple, vuln-type-based explanation (1-2 sentences)
   - Uses `impact_summary` from backend if available
   - Falls back to vuln-type mapping if not provided
   - Written in plain language for non-security people
   - Examples:
     - XSS: "An attacker can run JavaScript in the user's browser and steal sessions or act as the user."
     - SQLi: "An attacker can read or modify application data in the database."

4. **HOW TO FIX IT:**
   - Label: "How to fix it"
   - Content: 
     - Short summary paragraph (`remediation_summary`)
     - Bullet list of steps (`remediation_steps` or `default_remediation_steps`)
   - Uses backend-provided remediation if available
   - Falls back to vuln-type-based default steps if empty
   - Examples:
     - XSS: "HTML-encode user input before rendering", "Avoid inserting raw user input into HTML"
     - SQLi: "Use prepared statements / parameterized queries", "Avoid building SQL queries by string concatenation"

**Header:**
- Severity badge
- Status badge (Open/Resolved/etc.)
- Lifecycle badge ("Present in latest scan" / "Not seen in latest scan")
- Title focused on vulnerability (not tool), e.g., "Cross-Site Scripting (XSS) on /login.php"
- vuln_type badge (if available)

**Footer:**
- "Click for more details" hint (opens FindingDetailsDrawer)

**Tool Names:**
- **NOT shown in the main card view**
- Only visible in "Technical details" collapsible section in FindingDetailsDrawer

**FindingDetailsDrawer Structure:**
- Same 4 sections with more room
- "Technical details" collapsible section:
  - Tool name ("Detected by: dalfox/nuclei/sqlmap")
  - Evidence table (raw_data_preview)
  - Full raw_data JSON (collapsible)

**Copy Improvements:**
- "What we found" instead of "Vulnerability description"
- "Why it matters" instead of "Risk statement"
- "How to fix it" instead of "Remediation"
- "Technical details" instead of "Advanced details"
- "Detected by" instead of "Found by"

