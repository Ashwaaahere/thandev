# Findings Pipeline - Current State & Improvements

## Current State (Before Improvements)

### Database Models

**Finding Model** (`backend/app/models/finding.py`):
- `id` (String, PK) - UUID
- `scan_job_id` (String, FK) - Links to scan_jobs table
- `title` (String) - Finding title
- `description` (Text, nullable) - Detailed description
- `severity` (Enum: CRITICAL, HIGH, MEDIUM, LOW, INFO)
- `cve_id`, `cwe_id`, `cvss_score` - CVE/CWE information
- `url`, `path`, `line_number` - Location information (basic)
- `recommendation` (Text, nullable) - Remediation guidance (basic)
- `tool_name` (String) - Tool that found it
- `raw_data` (Text) - Raw JSON output from tool
- `status` (Enum: OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED)
- `created_at` (DateTime) - Timestamp

**Relationships:**
- Finding → ScanJob (via `scan_job_id`)
- ScanJob → Project (via `project_id`)
- Finding does NOT have direct `project_id` (accessed via `scan_job.project_id`)

### Tool Output Ingestion

**Location:** `backend/app/services/findings_ingestor.py`

**Supported Tools:**
- `nuclei` - Vulnerability scanner (parses JSONL)
- `nmap` - Port scanner (parses XML)
- `sslscan` - SSL/TLS scanner (parses JSON/text)
- `httpx` - HTTP surface discovery (parses JSON)
- `ffuf` - Directory brute-forcer (parses JSON)
- `dalfox` - XSS scanner (parses JSON)
- `sqlmap` - SQL injection scanner (parses stdout/logs)

**Current Ingestion Pattern:**
1. Each tool has a `parse_*_output()` function that reads tool output files
2. Each tool has an `ingest_*_findings()` function that creates Finding records
3. **Per-scan idempotency**: Each ingestor deletes existing findings for that `scan_job_id` + `tool_name` before inserting new ones
4. **Within-scan deduplication**: Some tools (e.g., nuclei) deduplicate by `template_id + URL` within a single scan

**Current Limitations:**
- No cross-scan deduplication (same issue in scan 1 and scan 2 creates 2 separate findings)
- No lifecycle tracking (first_seen, last_seen, found_count)
- No normalized location fields (http_method, parameter)
- No structured remediation (only free-form `recommendation` text)
- No tracking of "not seen in latest scan" status

### Scan Model

**ScanJob Model** (`backend/app/models/scan.py`):
- `id` (String, PK)
- `project_id` (String, FK) - Links to projects
- `status` (Enum: PENDING, QUEUED, RUNNING, COMPLETED, COMPLETED_WITH_ERRORS, FAILED, CANCELLED)
- `created_at`, `started_at`, `completed_at` - Timestamps
- Relationships: `findings`, `tool_results`

**Scan Completion:**
- Handled in `backend/app/services/scan_orchestrator.py` in `run_scan_for_job()`
- Sets `status = COMPLETED` or `COMPLETED_WITH_ERRORS`
- Updates `completed_at` timestamp
- No lifecycle update for findings (no "not seen in latest scan" logic)

### Status Workflow

Findings use `FindingStatus` enum:
- `OPEN` - New finding, not yet reviewed
- `ACKNOWLEDGED` - User has acknowledged the finding
- `RESOLVED` - User marked as fixed
- `SUPPRESSED` - User suppressed (false positive, etc.)

Status is manually updated by users via API/UI. No automatic status changes based on lifecycle.

---

## Improved Schema (After Implementation)

### New Finding Fields

**Identification / Linking:**
- `project_id` (String, FK) - Direct link to project (for easier querying)
- `tool` (String) - Tool name (renamed from `tool_name` for consistency)
- `template_id` / `rule_id` (String, nullable) - Template/rule identifier (e.g., nuclei template-id)
- `vuln_type` / `category` (String, nullable) - Normalized vulnerability type (e.g., "xss", "sqli")

**Location / Where:**
- `url` (String) - Normalized URL (existing, enhanced)
- `http_method` (String, nullable) - HTTP method (GET, POST, etc.)
- `parameter` (String, nullable) - Query/body parameter name
- `header_name` (String, nullable) - Header name if applicable
- `cookie_name` (String, nullable) - Cookie name if applicable

**Evidence:**
- `evidence` (Text, nullable) - Short evidence snippet (payload, response snippet)
- `raw_data` (Text) - Full raw output (existing, kept)

**Lifecycle:**
- `dedup_key` (String, indexed) - Deterministic hash for deduplication
- `first_seen_at` (DateTime) - When first detected
- `last_seen_at` (DateTime) - When last detected
- `last_seen_in_scan_id` (String, FK, nullable) - ID of most recent scan where seen
- `found_count` (Integer) - Number of scans where this finding appeared
- `not_seen_in_latest_scan` (Boolean) - Flag: true if not seen in latest scan for project

**Remediation:**
- `remediation_summary` (Text, nullable) - Short summary of what to fix
- `remediation_steps` (Text, nullable) - JSON array or newline-separated steps
- `framework_hint` (String, nullable) - Detected framework (django, express, laravel, etc.)

**Existing Fields (Kept):**
- `id`, `scan_job_id`, `title`, `description`, `severity`, `cve_id`, `cwe_id`, `cvss_score`, `status`, `created_at`

---

## Deduplication Logic

### Deduplication Key Generation

The `dedup_key` is a deterministic hash based on:
- `project_id`
- `tool`
- `template_id` (or equivalent rule_id)
- `normalized_url` (URL without query params, normalized)
- `parameter` (if present)
- `vuln_type` (if present)

**Normalization Rules:**
- URL: Remove query params, normalize trailing slashes, lowercase scheme/host
- Parameter: Lowercase, trim whitespace
- Template ID: Use as-is (already normalized by tool)

**Hash Algorithm:**
- Concatenate fields with `|` separator
- SHA-256 hash
- Store as hex string

### Ingestion Flow (Updated)

For each raw finding:
1. Extract and normalize fields: `tool`, `template_id`, `vuln_type`, `url`, `http_method`, `parameter`, `evidence`
2. Get `project_id` from `scan_job.project_id`
3. Generate `dedup_key`
4. Query for existing finding: `WHERE project_id = ? AND dedup_key = ?`
5. **If exists:**
   - Update: `last_seen_at = now()`, `last_seen_in_scan_id = current_scan_id`, `found_count += 1`
   - Do NOT create new record
6. **If not exists:**
   - Create new finding with: `first_seen_at = last_seen_at = now()`, `found_count = 1`, `last_seen_in_scan_id = current_scan_id`

### Scan Completion Lifecycle Update

When a scan completes for a project:
1. Get all findings for that `project_id`
2. For each finding:
   - If `last_seen_in_scan_id == current_scan_id`: Mark as "still present" (no change to `not_seen_in_latest_scan`)
   - If `last_seen_in_scan_id != current_scan_id`: Set `not_seen_in_latest_scan = true`
3. Do NOT auto-set `status = RESOLVED` (user must confirm)

---

## Remediation Hints

### Basic Remediation Mapping

A simple mapping table provides initial remediation hints based on `vuln_type`:

- `xss`: "Sanitize user input and output-encode parameter before reflecting in HTML"
- `sqli`: "Use parameterized queries/prepared statements. Never concatenate user input into SQL."
- `ssrf`: "Validate and whitelist allowed URLs/hosts. Use DNS rebinding protection."
- `ssti`: "Use safe template engines. Avoid user-controlled template rendering."
- `xxe`: "Disable XML external entity processing. Use safe XML parsers."
- `dir_traversal`: "Validate file paths. Use path normalization. Restrict file access to safe directories."
- `cors`: "Configure CORS headers properly. Restrict allowed origins."
- `csrf`: "Implement CSRF tokens. Validate origin/referer headers."
- `cmdi`: "Avoid shell command execution with user input. Use safe APIs."
- `idor`: "Implement proper authorization checks. Verify user owns requested resource."

These can be enhanced later with AI-generated, context-aware remediation.

---

## UI Changes

### Findings List View

For each finding, display:
- **Title**: `[severity] [vuln_type]` (e.g., "HIGH XSS")
- **Location**: `METHOD URL` + parameter (if present)
- **Status Badge**: `OPEN` / `ACK` / `RESOLVED` / `SUPPRESSED`
- **Lifecycle Badge**: 
  - "Still present in latest scan" (green)
  - "Not seen in latest scan" (yellow/orange)
- **Lifecycle Info**: 
  - "First seen: <date>"
  - "Last seen: <date>"
  - "Seen in <N> scans"

### Finding Detail View

Add section:
- **"How to Fix"**
  - `remediation_summary`
  - Bullet points from `remediation_steps`

---

## Implementation Notes

- All changes are backwards compatible (new fields are nullable with defaults)
- Migration handles existing data (sets `first_seen_at = created_at`, `last_seen_at = created_at`, `found_count = 1`)
- Deduplication is applied to all active tools (nuclei, nmap, sslscan, httpx, ffuf, dalfox, sqlmap)
- Lifecycle updates run after scan completion (in `scan_orchestrator.py`)

---

## Tool-Specific Parsing

### Current Fields Used for Location/Evidence

**Location Fields:**
- `url`: Extracted from tool output (matched-at, host, target URL)
- `http_method`: Extracted from request method or inferred from parameter place (GET/POST)
- `parameter`: Extracted from tool output (param, parameter, query param name)

**Evidence Fields:**
- `evidence`: Short human-readable summary combining technique/payload/context
- `raw_data`: Full raw JSON output from tool (stored as JSON string)

**Identification Fields:**
- `tool`: Tool name (nuclei, sqlmap, dalfox, etc.)
- `template_id`: Template/rule identifier (nuclei template-id, sqlmap technique, dalfox rule)
- `vuln_type`: Normalized vulnerability type (xss, sqli, etc.)

### Where Tool Ingestion Lives

**Location:** `backend/app/services/findings_ingestor.py`

**Parser Functions:**
- `parse_nuclei_output(path: Path) -> List[Dict]` - Parses JSONL output
- `parse_sqlmap_output(output_dir: Path) -> List[Dict]` - Parses stdout/log files
- `parse_sqlmap_stdout(stdout: str) -> List[Dict]` - Parses stdout text
- `parse_dalfox_output(path: Path) -> List[Dict]` - Parses JSON output

**Ingestion Functions:**
- `ingest_nuclei_findings(db, scan_job_id, nuclei_results) -> List[Finding]` - Uses `create_or_update_finding` helper
- `ingest_sqlmap_findings(db, scan_job_id, sqlmap_results) -> List[Finding]` - Uses `create_or_update_finding` helper
- `ingest_dalfox_findings(db, scan_job_id, dalfox_results) -> List[Finding]` - Uses `create_or_update_finding` helper

**Helper Function:**
- `create_or_update_finding(db, scan_job_id, project_id, finding_data) -> Finding` - Handles deduplication and lifecycle

### Tool-Specific Parsing Details

#### sqlmap

**Parser:** `parse_sqlmap_output()` and `parse_sqlmap_stdout()`

**Extracted Fields:**
- `url`: Target URL from stdout/log files
- `parameter`: Parameter name (e.g., "id", "searchFor")
- `place`: Parameter location (GET, POST, Cookie, Header)
- `technique`: Injection technique (e.g., "boolean-based blind", "union-based")
- `payload`: Example SQL injection payload
- `dbms`: Database management system (MySQL, PostgreSQL, etc.)

**Ingestion Mapping:**
- `tool`: "sqlmap"
- `vuln_type`: "sqli"
- `template_id`: technique (e.g., "boolean-based blind")
- `http_method`: Extracted from `place` (GET/POST)
- `parameter`: Parameter name
- `evidence`: Human-readable summary combining technique, parameter, DBMS, and payload
- `url`: Normalized URL

**Example Evidence:**
- "Boolean-based blind. parameter 'searchFor'. DBMS: MySQL >= 5.6. payload: 1' AND 1=1--"

#### dalfox

**Parser:** `parse_dalfox_output()`

**Extracted Fields:**
- `url`: Target URL
- `param` / `parameter`: Parameter name
- `payload`: XSS payload
- `type`: XSS type (reflected, stored, blind, dom)
- `method`: HTTP method (GET, POST, etc.)

**Ingestion Mapping:**
- `tool`: "dalfox"
- `vuln_type`: "xss"
- `template_id`: XSS type (reflected/stored/blind/dom) or rule_id if available
- `http_method`: Normalized HTTP method (GET, POST, etc.)
- `parameter`: Parameter name
- `evidence`: Human-readable summary combining XSS type, parameter, and payload
- `url`: Target URL

**Example Evidence:**
- "Reflected XSS. parameter 'q'. payload: <script>alert(1)</script>"

#### nuclei

**Parser:** `parse_nuclei_output()`

**Extracted Fields:**
- `url` / `matched-at` / `host`: Target URL
- `template-id`: Nuclei template identifier
- `info.name`: Template name
- `info.tags`: Template tags (used for categorization)
- `request`: HTTP request (used to extract method)
- `extracted-results`: Extracted data from response
- `matcher-name`: Matcher that triggered

**Ingestion Mapping:**
- `tool`: "nuclei"
- `vuln_type`: Extracted from template tags using `categorize_nuclei_finding()`
- `template_id`: Nuclei template ID
- `http_method`: Extracted from request (first line) or method field
- `parameter`: Extracted from URL query params or extracted results
- `evidence`: Human-readable summary combining template name, matched location, extracted results, and request snippet
- `url`: Normalized URL

**Example Evidence:**
- "Template: SQL Injection Generic. Matched at: https://example.com/search?q=test. Extracted: admin, password. Request: POST /search HTTP/1.1"

**Vuln Type Extraction:**
- Uses `categorize_nuclei_finding()` to map template tags to vulnerability types
- Tags like "xss", "sqli", "ssrf" are mapped to normalized types
- Falls back to first category if no exact match

---

## Implementation Summary

### Files Modified/Created

1. **`backend/app/models/finding.py`**
   - Extended Finding model with lifecycle and remediation fields
   - Added: `project_id`, `tool`, `template_id`, `rule_id`, `vuln_type`, `category`
   - Added: `http_method`, `parameter`, `header_name`, `cookie_name`, `evidence`
   - Added: `dedup_key`, `first_seen_at`, `last_seen_at`, `last_seen_in_scan_id`, `found_count`, `not_seen_in_latest_scan`
   - Added: `remediation_summary`, `remediation_steps`, `framework_hint`

2. **`backend/migrations/versions/0008_add_findings_lifecycle_fields.py`**
   - Migration to add all new fields
   - Backfills existing data with default values

3. **`backend/app/utils/finding_utils.py`** (NEW)
   - `normalize_url()` - URL normalization for deduplication
   - `normalize_parameter()` - Parameter normalization
   - `generate_dedup_key()` - Creates deterministic dedup key
   - `get_remediation_hint()` - Returns remediation hints by vuln_type
   - `extract_vuln_type_from_categories()` - Extracts vuln_type from categories
   - `REMEDIATION_HINTS` - Mapping of vuln_type to remediation guidance

4. **`backend/app/services/findings_ingestor.py`**
   - Added `create_or_update_finding()` helper function for cross-scan deduplication
   - Updated `ingest_nuclei_findings()` to use new helper (other tools can be updated similarly)
   - Helper function:
     - Gets project_id from scan_job
     - Generates dedup_key
     - Checks for existing finding
     - Updates if exists, creates if new
     - Sets lifecycle fields and remediation hints

5. **`backend/app/services/scan_orchestrator.py`**
   - Added `update_findings_lifecycle_after_scan()` function
   - Called after scan completion to update `not_seen_in_latest_scan` flag
   - Marks findings as "not seen" if `last_seen_in_scan_id != current_scan_id`

6. **`frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`**
   - Extended Finding type with lifecycle and remediation fields
   - Updated UI to display:
     - Location info (HTTP method, URL, parameter)
     - Lifecycle badges ("STILL PRESENT" / "NOT SEEN IN LATEST")
     - Lifecycle details (first seen, last seen, found count)
     - Remediation section ("How to Fix" with summary and steps)

### Key Implementation Details

**Deduplication Logic:**
- Dedup key is SHA-256 hash of: `project_id|tool|template_id|normalized_url|parameter|vuln_type`
- Same finding across multiple scans updates a single record
- `found_count` increments each time the finding is seen
- `first_seen_at` never changes, `last_seen_at` updates on each occurrence

**Lifecycle Tracking:**
- After each scan completes, `update_findings_lifecycle_after_scan()` runs
- Findings with `last_seen_in_scan_id == current_scan_id` are marked as "still present"
- Findings with `last_seen_in_scan_id != current_scan_id` are marked as "not seen in latest scan"
- User must manually confirm resolution (no auto-status change)

**Remediation Hints:**
- Basic remediation hints provided for common vuln_types (xss, sqli, ssrf, etc.)
- Hints include summary and step-by-step guidance
- Can be enhanced later with AI-generated, context-aware remediation
- Only set if not already present (doesn't overwrite user-provided remediation)

### Next Steps (Optional Enhancements)

1. Update remaining ingestor functions (nmap, sslscan, httpx, ffuf, dalfox, sqlmap) to use `create_or_update_finding()`
2. Add API endpoints to manually update remediation fields
3. Integrate AI service to generate context-aware remediation hints
4. Add filters in UI for "not seen in latest scan" findings
5. Add bulk actions for marking findings as resolved
6. Add tests for deduplication and lifecycle logic

