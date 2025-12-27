# Thandev Backend

## Scope

The Thandev backend is a FastAPI application located in `backend/app/`. It provides REST API endpoints, orchestrates security scans, manages findings lifecycle, and generates PDF reports.

## Main Entrypoint

**File**: `backend/app/main.py`

**Application Factory**: FastAPI app created with:
- Title: "Thandev v2"
- Version: "2.0.0"
- Lifespan context manager for startup/shutdown
- CORS middleware for frontend communication
- GZip compression middleware

**Startup Behavior:**
- Creates database tables (SQLite development only; Postgres uses Alembic migrations)
- Optionally recovers stale scans on startup (if `SCAN_RECOVERY_ENABLED=true`)
- Logs environment and service configuration

**Run Command:**
```bash
uvicorn app.main:app --reload --port 8000
```

## Important Subpackages

### `api/` - REST API Route Handlers

FastAPI routers organized by domain:

- **`projects.py`**: Project CRUD operations
- **`scans.py`**: Scan management, execution, and results
- **`findings.py`**: Findings listing, filtering, and status updates
- **`tenants.py`**: Tenant plan information and usage
- **`metrics.py`**: Dashboard statistics
- **`notifications.py`**: User notifications
- **`performance.py`**: Performance scan endpoints
- **`findings_batch.py`**: Batch finding retrieval

### `models/` - SQLAlchemy ORM Models

Database models using SQLAlchemy 2.0:

- **`project.py`**: `Project` model (target URLs, metadata)
- **`scan.py`**: `ScanJob` model (scan execution records)
- **`finding.py`**: `Finding` and `ToolResult` models
- **`user.py`**: `User` model (authentication)
- **`tenant.py`**: `Tenant` model (multi-tenancy)
- **`notification.py`**: `Notification` model
- **`performance_scan.py`**: `PerformanceScan` model
- **`audit_log.py`**: `AuditLog` model

### `schemas/` - Pydantic Request/Response Models

API validation and serialization:

- **`project.py`**: `ProjectCreate`, `ProjectResponse`, `ProjectWithStats`
- **`scan.py`**: `ScanCreate`, `ScanResponse`, `ScanJobListItem`
- **`finding.py`**: `FindingListItem`, `FindingDetailResponse`, `UpdateFindingStatusRequest`
- **`tenant.py`**: `TenantPlanInfo`, `TenantPlanUsage`

### `services/` - Business Logic

Core service modules:

- **`scan_orchestrator.py`**: Scan execution coordination
- **`findings_ingestor.py`**: Tool output parsing and findings ingestion
- **`pdf_reports.py`**: PDF report generation (full and executive)
- **`brain_client.py`**: HTTP client for Brain service
- **`tools.py`**: Tool executor abstraction
- **`scan_profiles.py`**: Scan level tool selection
- **`scan_recovery.py`**: Stale scan recovery logic
- **`queue_manager.py`**: Redis-based queue management
- **`finding_enrichment.py`**: AI finding enrichment (if enabled)

### `core/` - Core Infrastructure

- **`config.py`**: Settings and environment variables (`Settings` class)
- **`database.py`**: Database connection, session management, `get_db()` dependency
- **`tenant_utils.py`**: Tenant/user authentication helpers (`require_tenant`, `get_current_user`)
- **`plans.py`**: Plan limits and tier definitions
- **`tool_matrix.py`**: Tool selection matrix for scan levels
- **`scan_timeouts.py`**: Tool timeout configuration

### `tasks/` - Celery Background Tasks

- **`celery_app.py`**: Celery application configuration
- Task: `run_scan_task(scan_job_id, target_url, scan_level, user_id)`

### `utils/` - Utility Functions

- **`finding_response_builder.py`**: Location extraction, impact summaries, remediation data
- **`http_security.py`**: HTTP security header utilities
- **`request_recorder.py`**: Request logging utilities

## API Surface

### Projects (`/api/projects`)

**Endpoints:**
- `POST /api/projects`: Create new project
  - Request: `{name, target_url, repo_url?, description?}`
  - Response: `ProjectResponse`
- `GET /api/projects`: List projects with statistics
  - Query params: `limit`, `offset`
  - Response: `ProjectListWithStatsResponse`
- `GET /api/projects/{id}`: Get project details
  - Response: `ProjectResponse`
- `GET /api/projects/{id}/overview`: Get project overview with scan history
  - Response: `ProjectOverviewResponse` (includes stats and recent scans)

**Authentication**: Requires `X-Thandev-User-Id` or `X-Thandev-Tenant-Id` header

### Scans (`/api/scans`)

**Endpoints:**
- `POST /api/scans`: Create and queue a scan
  - Request: `{project_id, scan_level: "basic"|"pro"|"advanced"}`
  - Response: `ScanResponse` with `id` and `status: "queued"`
- `GET /api/scans`: List scans (paginated)
  - Query params: `limit`, `offset`
  - Response: `ScanJobListResponse` (lightweight scan items)
- `GET /api/scans/{id}`: Get scan details
  - Response: `ScanResponse` (full scan info with summary)
- `GET /api/scans/{id}/findings`: Get scan findings (paginated)
  - Query params: `limit`, `offset`, `severity?`, `tool?`, `status?`
  - Response: `FindingListResponse`
- `GET /api/scans/{id}/report.pdf`: Download PDF report
  - Query params: `mode: "full"|"executive"`
  - Response: Streaming PDF file
- `GET /api/scans/{id}/tools`: Get tool execution statuses
  - Response: `ScanToolsResponse` (list of `ToolExecutionResult`)
- `PATCH /api/scans/{id}/cancel`: Cancel a running scan
  - Response: `ScanResponse` with updated status

**Authentication**: Requires tenant/user context

### Findings (`/api/findings`)

**Endpoints:**
- `GET /api/findings`: List findings with filters
  - Query params: `severity?`, `search?`, `tool?`, `project_id?`, `scan_id?`, `status?`, `category?`, `vuln_type?`, `limit`, `offset`
  - Response: `FindingListResponse`
- `GET /api/findings/{id}`: Get finding details
  - Response: `FindingDetailResponse` (includes location, impact, remediation)
- `PATCH /api/findings/{id}/status`: Update finding status
  - Request: `{status: "open"|"acknowledged"|"resolved"|"suppressed"}`
  - Response: `FindingDetailResponse`

**Authentication**: Requires tenant/user context

### Tenants (`/api/tenants`)

**Endpoints:**
- `GET /api/tenants/current`: Get current tenant plan information
  - Response: `TenantPlanInfo` (plan, limits, usage statistics)

**Authentication**: Requires tenant context

### Metrics (`/api/metrics`)

**Endpoints:**
- `GET /api/metrics/dashboard`: Get dashboard statistics
  - Response: Dashboard overview with scan counts, finding counts, risk scores

**Authentication**: Requires tenant/user context

## Scan Orchestration

### Scan Creation Flow

1. **User Request**: Frontend POST `/api/scans` with `{project_id, scan_level}`
2. **Backend**: Creates `ScanJob` record with status `pending`
3. **Stack Info Collection**: Performs HTTP HEAD/GET to collect target metadata
4. **Brain Service Call** (if enabled):
   - POST `/v1/plan-scan` with `{target_url, scan_level, stack_info}`
   - Receives `PlanScanResponse` with tool steps
   - Stores plan in `ScanJob.ai_plan` (JSON)
5. **Queue Scan**: Routes to Celery task or Redis stream
6. **Response**: Returns `ScanResponse` with scan ID

### Tool Selection

**Scan Levels:**
- **basic**: Fast scan with `nuclei` (basic HTTP vulnerability scanning)
- **pro**: Includes `nuclei` + `nmap` (host/service discovery)
- **advanced**: All tools (`nuclei`, `nmap`, `sslscan`, `httpx`, `ffuf`, `dalfox`, `sqlmap`)

**Tool Matrix**: Defined in `app/core/tool_matrix.py`
- Maps scan levels to enabled tools
- Each tool has execution modes (e.g., `nuclei-fast`, `nuclei-deep`)
- Tool selection respects scan level and Brain service plan (if available)

### Scan Execution

**Path 1: Celery (Primary)**
```
Celery Task → run_scan_for_job() → ToolExecutor → Parallel Tool Execution → Findings Ingestion
```

**Path 2: Redis Streams (Alternative)**
```
Backend → Redis Stream → Runner Service → Tool Execution → Findings Ingestion
```

**Execution Details:**
- Tools run in parallel (up to `MAX_PARALLEL_TOOLS=5`)
- Each tool has configurable timeout (per scan level)
- Tool outputs saved to files in scan job directory
- Findings ingested immediately after each tool completes
- Scan status updated: `pending` → `queued` → `running` → `completed` (or `failed`)

### Timeouts and Error Handling

**Timeout Configuration:**
- `MAX_SCAN_TIMEOUT_SECONDS`: 3600 (1 hour total)
- `TOOL_EXECUTION_TIMEOUT_SECONDS`: 900 (15 minutes per tool)
- Per-tool timeouts defined in `app/core/scan_timeouts.py`

**Error Handling:**
- Tool failures don't stop entire scan
- Failed tools recorded in `ToolResult` with `status: "failed"`
- Scan continues with remaining tools
- Scan marked `failed` only if critical errors occur

## Findings Ingestion & Lifecycle

### Ingestion Process

**Location**: `app/services/findings_ingestor.py`

**Supported Tools:**
- `nuclei`: JSON output parsing
- `nmap`: XML output parsing
- `sslscan`: JSON output parsing
- `httpx`: JSON output parsing
- `ffuf`: JSON output parsing
- `dalfox`: JSON output parsing
- `sqlmap`: JSON output parsing

**Process:**
1. Tool output file read (JSON/XML)
2. Parser extracts structured data (vulnerability details, URLs, parameters)
3. For each finding:
   - Create `Finding` record with:
     - `title`, `description`, `severity`
     - `url`, `http_method`, `parameter` (location data)
     - `vuln_type` (xss, sqli, etc.)
     - `tool_name`, `raw_data` (JSON string)
   - Check for existing finding (deduplication)
   - Update or create finding with lifecycle fields

### Deduplication

**Strategy**: Findings are deduplicated based on:
- `project_id`
- `title` (normalized)
- `url` (normalized)
- `parameter` (if present)

**Lifecycle Fields:**
- `first_seen_at`: First occurrence timestamp
- `last_seen_at`: Most recent occurrence timestamp
- `found_count`: Number of times found across scans
- `not_seen_in_latest_scan`: Boolean flag (set if not found in latest scan)

**Status Management:**
- `status`: `open`, `acknowledged`, `resolved`, `suppressed`
- User can update status via API
- Status persists across scans

### Finding Enrichment

**Location**: `app/utils/finding_response_builder.py`

**Functions:**
- `extract_location_from_raw_data()`: Extracts URL, HTTP method, parameter from `raw_data` JSON
- `get_impact_summary()`: Returns impact text (AI-enriched or static fallback)
- `get_remediation_data()`: Returns remediation summary and steps (AI-enriched or static fallback)

**Enrichment Sources:**
1. **AI-Enriched** (if available): `impact_summary`, `remediation_summary`, `remediation_steps` from database
2. **Static Fallbacks**: Tool/vulnerability-specific defaults (e.g., XSS remediation steps)
3. **Generic**: Generic remediation hints from `finding_utils`

## Reporting

### PDF Report Generation

**Location**: `app/services/pdf_reports.py`

**Function**: `generate_scan_report_pdf(scan_job_id, mode: "full"|"executive", db)`

**Report Modes:**
- **full**: Complete technical report with all findings, tool outputs, recommendations
- **executive**: High-level summary with risk score, top findings, recommendations

**Report Sections:**
1. **Cover Page**: Scan metadata, target URL, scan level, date
2. **Executive Summary**: Risk score, findings count by severity, top findings
3. **Findings Detail**: Detailed finding descriptions with:
   - Location (URL, method, parameter)
   - Impact summary
   - Remediation steps
   - Severity indicators
4. **Tool Execution Summary**: Tool statuses, execution times
5. **Recommendations**: Prioritized remediation guidance

**Technology**: ReportLab Platypus for PDF generation

**Endpoint**: `GET /api/scans/{id}/report.pdf?mode=full|executive`

## Configuration

### Important Environment Variables

**Database:**
- `DATABASE_URL`: Connection string (default: `sqlite:///./thandev.db` for dev, Postgres for production)
- `ENVIRONMENT`: `development`, `production`, `docker`, `testing`

**Redis:**
- `REDIS_URL`: Redis connection (default: `redis://localhost:6379/0`)
- Used for Celery broker/result backend and Redis streams

**Brain Service:**
- `BRAIN_SERVICE_URL`: Brain service URL (default: `http://localhost:8001`)
- `BRAIN_SERVICE_ENABLED`: Enable/disable brain service (default: `true`)
- `BRAIN_REQUIRED`: Fail scan if brain unavailable (default: `false`)
- `BRAIN_SERVICE_TIMEOUT`: Request timeout in seconds (default: `30`)

**OpenAI:**
- `OPENAI_API_KEY`: API key for AI features (optional)

**Scan Execution:**
- `MAX_PARALLEL_TOOLS`: Maximum parallel tool executions (default: `5`)
- `MAX_SCAN_TIMEOUT_SECONDS`: Total scan timeout (default: `3600`)
- `TOOL_EXECUTION_TIMEOUT_SECONDS`: Per-tool timeout (default: `900`)

**Findings:**
- `MAX_INDIVIDUAL_FINDINGS_PER_SCAN`: Maximum findings per scan (default: `300`)
- `HIGH_RISK_PORTS`: Comma-separated high-risk ports (default: `"22,3389,5900"`)

**CORS:**
- `CORS_ORIGINS`: Comma-separated allowed origins (default: includes `localhost:3000`)

**Security:**
- `SECRET_KEY`: Secret key for JWT (change in production!)
- `ALGORITHM`: JWT algorithm (default: `HS256`)

### Feature Flags

- `BRAIN_SERVICE_ENABLED`: Enable/disable Brain service integration
- `SCAN_RECOVERY_ENABLED`: Enable stale scan recovery on startup
- `USE_JSON_LOGGING`: Use structured JSON logging (production)

## Database Migrations

**Tool**: Alembic

**Location**: `backend/migrations/`

**Commands:**
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Note**: In development with SQLite, tables may be auto-created. In production with Postgres, always use Alembic migrations.

