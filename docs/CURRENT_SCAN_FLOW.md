# Current Scan Flow

Complete documentation of the scan execution flow, tool execution, findings normalization, and artifact handling.

## Sequence Diagram (Text Format)

```
User/Frontend
    |
    | POST /api/v1/scans {project_id, scan_level}
    v
FastAPI Backend (app/api/scans.py)
    |
    | 1. Validate project exists, user has access
    | 2. Check plan limits (quota enforcement via app/core/plans.py)
    | 3. Create ScanJob record:
    |    - id: UUID
    |    - project_id: FK to projects
    |    - scan_level: basic|pro|advanced
    |    - status: PENDING
    |    - created_at: now()
    | 4. Queue Celery task via ScanOrchestrator.queue_scan()
    |    - Updates status: PENDING → QUEUED
    |    - Stores celery_task_id
    | 5. Return ScanResponse to frontend
    v
Celery Queue (Redis)
    |
    | Task: run_scan_task(scan_job_id, target_url, scan_level, user_id)
    | Broker: Redis (CELERY_BROKER_URL)
    | Queue: "celery" (default queue)
    v
Celery Worker (app/tasks/celery_app.py)
    |
    | 1. Acquire user scan slot via QueueManager (Redis lock)
    |    - Max 3 concurrent scans per user
    |    - Uses Redis key: "user_scan_slots:{user_id}"
    |    - If limit exceeded: Retry task after 30 seconds
    | 2. Load ScanJob from database
    | 3. Update ScanJob:
    |    - status: QUEUED → RUNNING
    |    - started_at: now()
    | 4. Call run_scan_for_job(scan_job)
    v
Scan Orchestrator (app/services/scan_orchestrator.py::run_scan_for_job)
    |
    | 1. Load ScanJob from DB (refresh to get latest state)
    | 2. Get target_url from scan_job.project.target_url
    | 3. Build stack_info (HTTP HEAD/GET request to target):
    |    - Makes HTTP request to target_url
    |    - Captures: status_code, headers (Server, X-Powered-By, etc.)
    |    - Stores in scan_job.stack_info (JSON):
    |      {
    |        "target_url": "https://example.com",
    |        "scan_level": "pro",
    |        "http": {
    |          "status_code": 200,
    |          "headers": {"Server": "nginx", ...}
    |        }
    |      }
    |    - Commits to DB
    |
    | 4. Plan scan (two approaches):
    |    
    |    A. Brain Service Planning (NEW - if brain service available):
    |       - Calls brain service: POST /v1/plan-scan
    |       - Sends: target_url, scan_level, stack_info, prior_findings
    |       - Brain service:
    |         * Queries RAG store for relevant findings/tech stack
    |         * Applies deterministic rules (TLS → sslyze, etc.)
    |         * Returns Plan with steps[], timeline, reasons
    |       - Validates plan (tool existence, DAG acyclicity, policy limits)
    |       - Converts Plan to internal format with waves[]
    |
    |    B. Fallback Planning (LEGACY):
    |       - Uses tool_matrix.py to get base tools for scan_level
    |       - Applies heuristics:
    |         * Skip heavy tools if 5xx error
    |         * Skip SSL tools if not HTTPS
    |       - Returns plan with waves[] of tools
    |
    | 5. Create job directory: data/jobs/{scan_job_id}/
    |    - Creates directory with retry logic (max 3 attempts)
    |    - Used for storing tool output files
    |
    | 6. Initialize ToolExecutor
    |
    | 7. Run HTTP security header checks (before other tools):
    |    - Calls fetch_http_security(target_url)
    |    - Analyzes headers for missing security headers
    |    - Creates Finding records via ingest_http_header_findings()
    |
    | 8. Execute tools from plan waves:
    |    
    |    For each wave in plan.waves:
    |      phase = wave.phase (e.g., "initial", "follow-up")
    |      tools = wave.tools (list of tool configs)
    |      
    |      For each tool in tools (parallel execution, max 3 concurrent):
    |        |
    |        | ThreadPoolExecutor.submit(_run_single_tool)
    |        v
    |        _run_single_tool(db, scan_job_id, executor, tool_config, target_url, job_dir, loop)
    |          |
    |          | 1. Create thread-local DB session (SessionLocal())
    |          | 2. Create thread-local event loop (asyncio.new_event_loop())
    |          | 3. Load ScanJob from this thread's DB session
    |          | 4. Extract tool_name and tool_config from tool_config dict
    |          | 5. Call ToolExecutor.run_tool(tool_name, target_url, scan_level, **config)
    |          v
    |          ToolExecutor (app/services/tools.py)
    |            |
    |            | Executes actual binary via subprocess or asyncio:
    |            | - nuclei: subprocess.run(["nuclei", "-u", target, "-json", ...])
    |            | - nmap: subprocess.run(["nmap", "-oX", "-", target, ...])
    |            | - sslscan: subprocess.run(["sslscan", target, ...])
    |            | - httpx: asyncio.create_subprocess_exec(["httpx", ...])
    |            | - ffuf: subprocess.run(["ffuf", ...])
    |            | - dalfox: subprocess.run(["dalfox", ...])
    |            | - sqlmap: subprocess.run(["sqlmap", ...])
    |            |
    |            | Captures:
    |            | - stdout/stderr → output string
    |            | - exit_code
    |            | - execution_time (seconds)
    |            | - timed_out (boolean)
    |            |
    |            | Returns result dict:
    |            | {
    |            |   "output": "...",
    |            |   "exit_code": 0,
    |            |   "execution_time": 45.2,
    |            |   "command": "nuclei -u https://example.com ...",
    |            |   "error_message": None
    |            | }
    |          |
    |          | 6. Create ToolResult record in DB:
    |          |    - tool_name, tool_version
    |          |    - output (truncated if too large)
    |          |    - exit_code, execution_time, timed_out
    |          |    - command, error_message
    |          |
    |          | 7. Write output to file:
    |          |    - Path: data/jobs/{scan_job_id}/{tool_name}_output.json
    |          |    - Format: Tool-specific (JSON, JSONL, XML converted to JSON)
    |          |
    |          | 8. Parse output → findings:
    |          |    - parse_nuclei_output(file_path) → List[Dict]
    |          |    - parse_nmap_output(file_path) → List[Dict]
    |          |    - parse_sslscan_output(file_path) → List[Dict]
    |          |    - parse_httpx_output(file_path) → List[Dict]
    |          |    - parse_ffuf_output(file_path) → List[Dict]
    |          |    - parse_dalfox_output(file_path) → List[Dict]
    |          |    - parse_sqlmap_output(file_path) → List[Dict]
    |          |
    |          | 9. Ingest findings:
    |          |    - ingest_nuclei_findings(db, scan_job_id, nuclei_results)
    |          |    - ingest_nmap_findings(db, scan_job_id, nmap_results)
    |          |    - ingest_sslscan_findings(db, scan_job_id, sslscan_results)
    |          |    - Similar for other tools
    |          |    - Each ingester:
    |          |      * Deletes existing findings for this tool (idempotent)
    |          |      * Creates Finding records with normalized fields
    |          |      * Stores raw_data (JSON string of original output)
    |          |
    |          | 10. Commit DB transaction
    |          |
    |          Return tool_name
    |
    | 9. After initial wave completes:
    |    Call AI planner: generate_scan_plan_for_job(db, scan_job)
    |    - Queries findings from DB for this scan
    |    - Builds findings summary JSON
    |    - Calls brain service: POST /v1/plan-scan (if available)
    |      OR calls OpenAI API directly (legacy)
    |    - Returns plan with next_tools[], attack_paths[], reasoning
    |    - Save to scan_job:
    |      * ai_plan: {next_tools: [], attack_paths: [], reasoning: "..."}
    |      * ai_status: "planned"
    |    - Commits to DB
    |
    | 10. Execute AI-planned second wave (if tools recommended):
    |     - Filter tools: must exist in ToolExecutor + allowed for scan level
    |     - Run tools in parallel (same as step 8)
    |
    | 11. Final Nuclei ingestion (idempotent):
    |     - Collects all Nuclei outputs from files
    |     - Re-ingests to ensure all findings captured
    |     - Deletes old + creates new (idempotent)
    |
    | 12. Generate AI report:
    |     - Calls brain service: POST /v1/build-report-prompt (if available)
    |       * Brain service:
    |         - Loads findings from core backend API
    |         - Queries RAG store for supporting evidence
    |         - Builds artifact index
    |         - Returns prompt package (system message, user content, JSON schema)
    |     - OR uses legacy generate_basic_report() (rule-based)
    |     - Calculates risk_score from findings
    |     - Builds executive_summary, top_risks, remediation_overview
    |     - Save to scan_job.summary (JSON):
    |       {
    |         "risk_score": 65.5,
    |         "findings_count": 42,
    |         "executive_summary": "...",
    |         "top_risks": ["XSS", "SQL Injection"],
    |         "severity_breakdown": {"critical": 2, "high": 8, ...},
    |         "remediation_overview": "..."
    |       }
    |     - Commits to DB
    |
    | 13. Update ScanJob:
    |     - status: RUNNING → COMPLETED (or COMPLETED_WITH_ERRORS if some tools failed)
    |     - completed_at: now()
    |     - Commits to DB
    |
    | 14. Create notification (scan completed) - if notification system enabled
    |
    v
Return to Celery Worker
    |
    | Return task result: {scan_job_id, status, findings_count, tools_run}
    v
User/Frontend
    |
    | GET /api/v1/scans/{scan_id}
    | Returns ScanResponse with:
    | - summary (JSON)
    | - findings (List[FindingResponse])
    | - stack_info (JSON)
    | - ai_plan (JSON)
    | - status, timestamps
    |
    | Frontend renders:
    | - Scan detail page with findings list
    | - Severity breakdown charts
    | - Risk score visualization
    | - Tool execution results
    | - AI plan visualization
```

## Where Tool Execution Happens

### Entry Point
- **Celery Task**: `app/tasks/celery_app.py::run_scan_task()`
  - Binds to Celery worker
  - Handles user concurrency control (Redis locks)
  - Calls orchestrator

### Orchestration Layer
- **Scan Orchestrator**: `app/services/scan_orchestrator.py::run_scan_for_job()`
  - Coordinates entire scan pipeline
  - Manages tool execution waves
  - Handles AI planning and reporting

### Execution Layer
- **ToolExecutor**: `app/services/tools.py::ToolExecutor`
  - Methods: `run_tool()`, `_run_nuclei()`, `_run_nmap()`, `_run_sslscan()`, etc.
  - Executes actual binaries via:
    - `subprocess.run()` for synchronous tools (nuclei, nmap, sslscan, ffuf, dalfox, sqlmap)
    - `asyncio.create_subprocess_exec()` for async tools (httpx)
  - Captures stdout/stderr, measures execution time
  - Handles timeouts and errors

### Parallel Execution
- **ThreadPoolExecutor**: Max 3 concurrent tools per wave (`MAX_PARALLEL_TOOLS = 3`)
- Each thread:
  - Gets its own DB session (`SessionLocal()`)
  - Gets its own event loop (for async tools)
  - Runs `_run_single_tool()` which calls `ToolExecutor.run_tool()`
  - Commits findings independently

### Tool Output Storage
- **File System**: `backend/data/jobs/{scan_job_id}/{tool_name}_output.json`
  - Nuclei: JSONL format (one JSON object per line)
  - Nmap: XML converted to JSON
  - SSLScan: JSON format
  - HTTPx: JSON format
  - FFuF: JSON format
  - Dalfox: JSON format
  - SQLMap: JSON format

- **Database**: `tool_results` table stores:
  - `output` (text): Raw stdout/stderr (may be truncated for large outputs)
  - `exit_code`, `execution_time`, `timed_out`
  - `command`: Actual command executed (for reproducibility)
  - `error_message`: If tool failed
  - `tool_name`, `tool_version`: Tool metadata

## Findings Normalization & Storage

### Normalization Pipeline

#### 1. Tool Output Parsing (`app/services/findings_ingestor.py`)

**Nuclei Parser** (`parse_nuclei_output()`):
- Reads JSONL file (one JSON object per line)
- Extracts:
  - `template_id`: Template identifier
  - `info.severity`: critical, high, medium, low, info
  - `info.name`: Template name
  - `info.description`: Template description
  - `info.classification.cve-id`: CVE identifier
  - `info.classification.cvss-score`: CVSS score
  - `matched-at`: URL where finding was detected
  - `info.tags`: Template tags (xss, sqli, etc.)
- Returns: List[Dict] with normalized fields

**Nmap Parser** (`parse_nmap_output()`):
- Parses XML output (converted to JSON)
- Extracts:
  - Open ports: `port.@portid`, `port.state.@state`
  - Services: `port.service.@name`, `port.service.@version`
  - OS detection: `os.osmatch.@name`
- Returns: List[Dict] with port/service information

**SSLScan Parser** (`parse_sslscan_output()`):
- Parses JSON output
- Extracts:
  - Certificate issues: expired, self-signed, weak signature
  - Cipher weaknesses: weak ciphers, deprecated protocols
  - TLS version support
- Returns: List[Dict] with SSL/TLS issues

**Other Parsers**:
- `parse_httpx_output()`: HTTP metadata (status codes, headers, redirects)
- `parse_ffuf_output()`: Discovered paths (directory brute-force results)
- `parse_dalfox_output()`: XSS findings (vulnerable parameters, payloads)
- `parse_sqlmap_output()`: SQL injection findings (vulnerable parameters, techniques)

#### 2. Finding Creation

**Nuclei Ingester** (`ingest_nuclei_findings()`):
- Deletes existing nuclei findings for this scan (idempotent)
- For each result:
  - Maps severity: `"critical"` → `Severity.CRITICAL`, etc.
  - Extracts CVE: `info.classification.cve-id` → `finding.cve_id`
  - Extracts CVSS: `info.classification.cvss-score` → `finding.cvss_score`
  - Extracts URL: `matched-at` → `finding.url`
  - Categorizes: `categorize_nuclei_finding(template_tags)` → `raw_data.categories`
  - Creates `Finding` record:
    - `title`: From `info.name` or template_id
    - `description`: From `info.description`
    - `severity`: Mapped enum
    - `cve_id`, `cvss_score`: From classification
    - `url`: From matched-at
    - `tool_name`: "nuclei"
    - `raw_data`: JSON string of original result
    - `scan_job_id`: Links to scan

**Other Ingesters**:
- `ingest_nmap_findings()`: Creates findings for open ports, services
- `ingest_sslscan_findings()`: Creates findings for SSL/TLS issues
- `ingest_httpx_findings()`: Creates findings for HTTP metadata
- `ingest_ffuf_findings()`: Creates findings for discovered paths
- `ingest_dalfox_findings()`: Creates findings for XSS vulnerabilities
- `ingest_sqlmap_findings()`: Creates findings for SQL injection vulnerabilities
- `ingest_http_header_findings()`: Creates findings for missing security headers

#### 3. Database Storage

- `Finding` records inserted into `findings` table
- Each finding linked to `scan_job_id` (FK)
- `raw_data` field stores original tool output (JSON string) for reference
- Indexes on: `scan_job_id`, `severity`, `tool_name`, `cve_id`, `status`

### Normalization Rules

**Severity Mapping**:
- Nuclei: `"critical"` → `CRITICAL`, `"high"` → `HIGH`, etc. (direct mapping)
- Nmap: Open ports → `INFO`, vulnerabilities → `MEDIUM`/`HIGH`
- SSLScan: Certificate issues → `HIGH`, weak ciphers → `MEDIUM`
- HTTPx: Redirects → `INFO`, errors → `MEDIUM`
- FFuF: Discovered paths → `INFO`
- Dalfox: XSS → `HIGH`/`CRITICAL`
- SQLMap: SQL injection → `CRITICAL`/`HIGH`

**CVE Extraction**:
- Nuclei: `info.classification.cve-id` → `finding.cve_id`
- CVSS: `info.classification.cvss-score` → `finding.cvss_score`
- Other tools: Extracted from descriptions/tags via regex

**Category Tagging**:
- Nuclei tags mapped via `NUCLEI_TAG_TO_CATEGORY` dictionary:
  - `"xss"` → `"xss"`
  - `"sqli"` → `"sqli"`
  - `"lfi"`, `"rfi"` → `"dir_traversal"`
  - `"ssrf"` → `"ssrf"`
  - `"ssti"` → `"ssti"`
  - `"xxe"` → `"xxe"`
  - `"cors"` → `"cors"`
  - `"csrf"` → `"csrf"`
  - `"cmdi"` → `"cmdi"`
  - `"idor"` → `"idor"`
- Stored in `raw_data.categories` array (JSON)

**URL Normalization**:
- Base URL from `project.target_url` + path from finding
- Stored in `finding.url` (max 2048 chars)
- Path stored separately in `finding.path` if applicable

**CWE Extraction**:
- Extracted from tool output when available
- Stored in `finding.cwe_id`

## What is an "Artifact" in This Codebase?

### Definition
An **artifact** is any output produced by a tool during scan execution.

### Types of Artifacts

#### 1. Tool Output Files
- **Location**: `backend/data/jobs/{scan_job_id}/{tool_name}_output.json`
- **Format**: Tool-specific (JSON, JSONL, XML converted to JSON)
- **Examples**:
  - `nuclei_output.json`: JSONL format (one JSON object per line) of vulnerability findings
  - `nmap_output.json`: XML converted to JSON (ports, services, OS detection)
  - `sslscan_output.json`: JSON format (SSL/TLS scan results, certificate issues)
  - `httpx_output.json`: JSON format (HTTP metadata, redirects, status codes)
  - `ffuf_output.json`: JSON format (directory brute-force results, discovered paths)
  - `dalfox_output.json`: JSON format (XSS scan results, vulnerable parameters)
  - `sqlmap_output.json`: JSON format (SQL injection results, vulnerable parameters)

#### 2. Database Records

**ToolResult** (`tool_results` table):
- `output`: Raw stdout/stderr (may be truncated for large outputs)
- `command`: Exact command executed (for reproducibility)
- `exit_code`, `execution_time`, `timed_out`
- `error_message`: If tool failed
- `tool_name`, `tool_version`: Tool metadata

**Finding** (`findings` table):
- `raw_data`: Original tool output (JSON string) - full original finding
- Normalized fields: `title`, `severity`, `cve_id`, `url`, etc.
- Links to `scan_job_id`

#### 3. Scan Metadata (JSON fields in `scan_jobs`)

**stack_info** (JSON):
- Target HTTP metadata (headers, status_code)
- Used for AI planning and tech stack detection
```json
{
  "target_url": "https://example.com",
  "scan_level": "pro",
  "http": {
    "status_code": 200,
    "headers": {"Server": "nginx", "X-Powered-By": "PHP/8.1"}
  }
}
```

**ai_plan** (JSON):
- AI-generated plan (next_tools, attack_paths, reasoning)
- Stored after initial wave completes
```json
{
  "next_tools": [
    {"key": "nuclei", "mode": "cve_fast", "params": {...}}
  ],
  "attack_paths": [...],
  "reasoning": "Found XSS vulnerabilities, recommend deeper SQL injection testing"
}
```

**summary** (JSON):
- AI-generated report (risk_score, executive_summary, top_risks)
- Stored after scan completes
```json
{
  "risk_score": 65.5,
  "findings_count": 42,
  "executive_summary": "...",
  "top_risks": ["XSS", "SQL Injection"],
  "severity_breakdown": {"critical": 2, "high": 8, "medium": 15, "low": 12, "info": 5},
  "remediation_overview": "..."
}
```

### Artifact Lifecycle

1. **Generation**: Tool execution produces output
   - Tool runs via `ToolExecutor.run_tool()`
   - Output captured from stdout/stderr

2. **Storage**:
   - File written to `data/jobs/{scan_job_id}/{tool_name}_output.json`
   - `ToolResult` record created in DB with metadata

3. **Parsing**: Tool-specific parser extracts structured data
   - `parse_nuclei_output()` → List[Dict]
   - `parse_nmap_output()` → List[Dict]
   - etc.

4. **Normalization**: Parser output → `Finding` records
   - Tool-specific ingester creates `Finding` records
   - Normalized fields extracted
   - `raw_data` stores original output

5. **Retrieval**:
   - Frontend requests findings via `/api/v1/scans/{scan_id}/findings`
   - Tool results via `/api/v1/scans/{scan_id}/tools`
   - Raw files accessible via file system (not exposed via API currently)
   - Brain service can reference artifacts via artifact_index in report prompts

### Artifact References

- Findings reference artifacts via:
  - `tool_name`: Which tool produced this finding
  - `raw_data`: Original tool output (for detailed view)
  - `url`: Where finding was detected
- Tool results reference artifacts via:
  - `output`: Raw stdout/stderr
  - `command`: How to reproduce the scan
- Brain service references artifacts via:
  - `artifact_index`: Map of artifact IDs to metadata
  - Used in report prompt generation

## Brain Service Integration

### Scan Planning (`/v1/plan-scan`)

**When**: Called during scan orchestration (step 4 in sequence)

**Input**:
- `target_url`: URL to scan
- `scan_level`: basic|pro|advanced
- `stack_info`: Target metadata (optional)
- `prior_findings`: Previous findings for this target (optional)

**Process**:
1. Queries RAG store for:
   - Latest findings for this target/project
   - Technology fingerprint
   - CVE templates
   - Artifact summaries
2. Applies deterministic rules:
   - TLS endpoint → sslyze
   - HTTP endpoint → httpx
   - CVE signals → nuclei cve_fast
3. Generates Plan with:
   - `steps[]`: Tool execution steps with dependencies
   - `timeline`: Estimated duration
   - `reasons`: Why each tool was selected
4. Validates plan:
   - Tool/mode existence in catalog
   - DAG acyclicity (no circular dependencies)
   - Policy limits (max tools, max duration)

**Output**: `Plan` schema with steps, timeline, reasons

### Report Prompt Generation (`/v1/build-report-prompt`)

**When**: Called after scan completes (step 12 in sequence)

**Input**:
- `scan_job_id`: Scan job identifier
- `finding_ids`: List of finding IDs to include
- `artifact_refs`: List of artifact references (optional)
- `org_id`, `project_id`: For filtering

**Process**:
1. Loads findings from core backend API:
   - Calls `/api/v1/findings/batch` with finding_ids
   - Normalizes findings to standard format
2. Queries RAG store for supporting evidence:
   - Similar findings from other scans
   - Technology stack information
   - CVE metadata
3. Builds artifact index:
   - Maps artifact IDs to metadata
   - Includes tool names, execution times
4. Generates prompt package:
   - `system_message`: Instructions for LLM
   - `user_content`: Project info, targets, findings, evidence
   - `report_json_schema`: Strict JSON schema for LLM output
   - `artifact_index`: Map of artifact references

**Output**: `BuildReportPromptResponse` with prompt package

**Note**: Brain service does NOT generate report JSON itself. It only prepares the prompt package for the core backend to send to OpenAI.

## Key Constraints & Design Decisions

1. **Tool Execution**:
   - Tools run as separate processes (not in-process)
   - Output captured via stdout/stderr
   - Timeouts enforced per tool (configurable)
   - Max 3 tools in parallel per wave

2. **Findings Ingestion**:
   - Idempotent: Re-running ingestion deletes old findings first
   - Tool-specific: Each tool has its own parser/ingester
   - Normalized: All findings follow same `Finding` schema
   - `raw_data` preserves original output for reference

3. **AI Planning**:
   - Happens AFTER initial tool execution
   - Uses findings to suggest follow-up tools
   - Plan stored in `scan_jobs.ai_plan` (JSON)
   - Brain service provides RAG-assisted planning

4. **Concurrency**:
   - Max 3 tools in parallel per wave (`MAX_PARALLEL_TOOLS`)
   - Per-user limit: Max 3 concurrent scans (Redis-based via QueueManager)
   - ThreadPoolExecutor for parallel tool execution
   - Each thread gets its own DB session and event loop

5. **Error Handling**:
   - Tool failures don't stop entire scan
   - Failed tools logged in `tool_results.error_message`
   - Scan status: `COMPLETED_WITH_ERRORS` if some tools failed
   - `FAILED` only if all tools fail or critical error occurs

6. **Artifact Storage**:
   - Files stored in `data/jobs/{scan_job_id}/`
   - Database stores metadata in `tool_results` table
   - Findings store original output in `raw_data` (JSON string)
   - Artifacts not exposed via API (file system access only)

7. **Brain Service**:
   - Optional: System works without brain service (fallback to legacy planning)
   - RAG store populated via indexing script
   - Brain service provides intelligent planning and report prompts
   - Core backend calls brain service via HTTP client
