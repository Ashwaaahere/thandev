# Repository Map

Complete overview of the Thandev security scanning platform repository structure, services, and data flow.

## Services List

### 1. Core Backend (`backend/`)
- **Type**: FastAPI application
- **Port**: 8000
- **Purpose**: Main API server, scan orchestration, database operations
- **Tech Stack**: FastAPI, SQLAlchemy, PostgreSQL/SQLite, Celery, Redis

### 2. Frontend (`frontend/`)
- **Type**: Next.js application
- **Port**: 3000
- **Purpose**: Web UI for managing projects, scans, and viewing reports
- **Tech Stack**: Next.js, React, TypeScript, TailwindCSS

### 3. Brain Service (`services/thandev-brain/`)
- **Type**: FastAPI microservice
- **Port**: 8001
- **Purpose**: RAG-powered scan planning and report prompt generation
- **Tech Stack**: FastAPI, Qdrant/pgvector, Sentence Transformers, OpenAI

### 4. Supporting Services (Docker Compose)
- **PostgreSQL**: Database (port 5432)
- **Redis**: Task queue and caching (port 6379)
- **Qdrant**: Vector database for RAG (port 6333)

## Key Directories & Files

### Backend Structure (`backend/`)

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entry point, router registration
│   ├── core/
│   │   ├── config.py              # Settings (Pydantic), environment variables
│   │   ├── database.py            # SQLAlchemy engine, session factory, Base
│   │   ├── tenant_utils.py        # Multi-tenant utilities (header-based)
│   │   ├── plans.py                # Subscription plan limits/quota enforcement
│   │   └── tool_matrix.py          # Tool selection per scan level
│   ├── api/                        # API routers
│   │   ├── scans.py                # Scan CRUD, PDF reports, quick scan
│   │   ├── projects.py             # Project management
│   │   ├── findings.py             # Finding management (list, update status)
│   │   ├── findings_batch.py       # Batch findings API (for brain service)
│   │   ├── tenants.py              # Tenant/plan information
│   │   ├── metrics.py              # Dashboard metrics
│   │   ├── performance.py          # Performance scan endpoints
│   │   └── notifications.py       # Notification endpoints
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── scan.py                 # ScanJob model (scan execution state)
│   │   ├── finding.py              # Finding, ToolResult models
│   │   ├── project.py               # Project model
│   │   ├── tenant.py                # Tenant/organization model
│   │   └── user.py                 # User authentication model
│   ├── schemas/                    # Pydantic request/response schemas
│   │   ├── scan.py                 # ScanCreate, ScanResponse, etc.
│   │   └── ...
│   ├── services/                   # Business logic
│   │   ├── scan_orchestrator.py    # Main scan execution coordinator
│   │   ├── tools.py                 # ToolExecutor (runs security tools)
│   │   ├── findings_ingestor.py    # Parses tool output → Finding records
│   │   ├── scan_profiles.py        # Legacy scan level profiles
│   │   ├── queue_manager.py        # Redis-based per-user concurrency control
│   │   ├── http_security.py        # HTTP security header checks
│   │   ├── pdf_reports.py          # PDF report generation
│   │   └── ai/                     # AI services
│   │       ├── planner.py           # AI scan planning (calls brain service)
│   │       ├── reporter.py          # AI report generation (calls brain service)
│   │       ├── openai_client.py     # OpenAI API client wrapper
│   │       └── brain_client.py      # Brain service HTTP client
│   ├── tasks/                      # Celery tasks
│   │   └── celery_app.py           # Celery app + run_scan_task
│   └── utils/                      # Utilities
├── migrations/                     # Alembic database migrations
│   └── versions/
│       ├── 0001_init.py            # Initial schema (threat_item, etc.)
│       ├── 0002_add_scan_jobs_table.py
│       ├── 0003_add_indexes_and_performance_scans.py
│       ├── 0004_add_timed_out_to_tool_results.py
│       └── 0005_add_ai_plan_fields_to_scan_jobs.py
├── data/jobs/                      # Tool output artifacts (JSON files)
│   └── {scan_job_id}/
│       ├── nuclei_output.json
│       ├── nmap_output.json
│       ├── sslscan_output.json
│       └── ...
├── alembic.ini                      # Alembic configuration
└── requirements.txt                 # Python dependencies
```

### Frontend Structure (`frontend/`)

```
frontend/
├── app/                            # Next.js app router
│   ├── dashboard/                  # Dashboard pages
│   │   ├── scan/
│   │   │   └── report/[job_id]/    # Scan report page
│   │   └── ...
│   ├── projects/                    # Project pages
│   │   └── [projectId]/
│   │       └── scans/               # Scan list and detail pages
│   └── api/                        # API routes (proxies to backend)
├── components/                     # React components
│   └── Dashboard/                  # Dashboard components
│       ├── ScanHistoryClient.tsx
│       ├── ReportsClient.tsx
│       └── ...
├── lib/                            # Utilities
│   ├── thandevApi.ts               # API client
│   └── formatDate.ts               # Date formatting
└── package.json                    # Node.js dependencies
```

### Brain Service Structure (`services/thandev-brain/`)

```
services/thandev-brain/
├── app/
│   ├── main.py                     # FastAPI app entry point
│   ├── api/
│   │   └── v1.py                   # API endpoints (/v1/health, /v1/catalog, etc.)
│   ├── core/
│   │   └── config.py               # Settings
│   ├── rag/                        # RAG implementation
│   │   ├── store.py                 # RagStore interface (Qdrant, PgVector)
│   │   ├── embeddings.py            # EmbeddingProvider (OpenAI, SentenceTransformers)
│   │   └── ingestion.py             # Document ingestion utilities
│   ├── planner/                     # Scan planning logic
│   │   └── plan.py                  # Plan generation with RAG
│   ├── report_prompt/               # Report prompt generation
│   │   ├── builder.py               # Prompt package builder
│   │   └── finding_loader.py       # Finding loader from core backend
│   └── schemas/                     # Internal schemas
├── packages/
│   └── thandev_schemas/             # Shared Pydantic schemas
│       ├── planning.py              # Plan, Step, ToolDefinition schemas
│       └── reporting.py              # Report prompt schemas
├── scripts/
│   └── index_findings.py            # Script to index findings into RAG
└── requirements.txt                 # Python dependencies
```

## How "Scan Run" is Represented and Stored

### ScanJob Model (`backend/app/models/scan.py`)

A scan run is represented by a `ScanJob` record in the `scan_jobs` table:

**Primary Fields:**
- `id` (UUID string, PK)
- `project_id` (FK → projects)
- `scan_level` (enum: basic, pro, advanced)
- `status` (enum: pending, queued, running, completed, completed_with_errors, failed, cancelled)
- `celery_task_id` (Celery task tracking)

**JSON Fields:**
- `summary` (JSON): AI-generated report
  ```json
  {
    "risk_score": 65.5,
    "findings_count": 42,
    "executive_summary": "...",
    "top_risks": ["XSS", "SQL Injection"],
    "severity_breakdown": {"critical": 2, "high": 8, ...}
  }
  ```
- `stack_info` (JSON): Target metadata
  ```json
  {
    "target_url": "https://example.com",
    "scan_level": "pro",
    "http": {
      "status_code": 200,
      "headers": {"Server": "nginx", ...}
    }
  }
  ```
- `ai_plan` (JSON): AI-generated scan plan
  ```json
  {
    "next_tools": [{"key": "nuclei", "mode": "cve_fast", ...}],
    "attack_paths": [...],
    "reasoning": "..."
  }
  ```

**Timestamps:**
- `created_at`: When scan was created
- `started_at`: When scan execution started
- `completed_at`: When scan finished

**Relationships:**
- `findings`: One-to-many → `Finding` records
- `tool_results`: One-to-many → `ToolResult` records
- `project`: Many-to-one → `Project`

### Scan Lifecycle States

1. **PENDING**: Created but not yet queued
2. **QUEUED**: Queued in Celery, waiting for worker
3. **RUNNING**: Currently executing tools
4. **COMPLETED**: All tools finished successfully
5. **COMPLETED_WITH_ERRORS**: Some tools failed, but scan finished
6. **FAILED**: Scan failed completely
7. **CANCELLED**: User cancelled scan

## Results Ingestion & Normalization

### Tool Output → Findings Pipeline

#### 1. Tool Execution (`app/services/tools.py`)

`ToolExecutor.run_tool()` executes security tools:
- **Tools**: nuclei, nmap, sslscan, httpx, ffuf, dalfox, sqlmap
- **Output**: Dict with `output`, `exit_code`, `execution_time`, `command`
- **Storage**: 
  - Raw output saved to `data/jobs/{scan_job_id}/{tool_name}_output.json`
  - `ToolResult` record created in DB with metadata

#### 2. File Storage

Tool output files stored in:
```
backend/data/jobs/{scan_job_id}/
├── nuclei_output.json      # JSONL format (one JSON object per line)
├── nmap_output.json         # XML converted to JSON
├── sslscan_output.json      # JSON format
├── httpx_output.json        # JSON format
├── ffuf_output.json         # JSON format
├── dalfox_output.json       # JSON format
└── sqlmap_output.json       # JSON format
```

#### 3. Parsing (`app/services/findings_ingestor.py`)

Tool-specific parsers extract structured data:
- `parse_nuclei_output()`: Parses JSONL, extracts CVE, severity, tags
- `parse_nmap_output()`: Parses XML/JSON, extracts open ports, services
- `parse_sslscan_output()`: Parses JSON, extracts SSL/TLS issues
- `parse_httpx_output()`: Parses JSON, extracts HTTP metadata
- `parse_ffuf_output()`: Parses JSON, extracts discovered paths
- `parse_dalfox_output()`: Parses JSON, extracts XSS findings
- `parse_sqlmap_output()`: Parses JSON, extracts SQL injection findings

Each parser returns a list of normalized finding dicts.

#### 4. Ingestion

Tool-specific ingesters create `Finding` records:
- `ingest_nuclei_findings()`: Creates Finding records from Nuclei output
- `ingest_nmap_findings()`: Creates Finding records from Nmap output
- `ingest_sslscan_findings()`: Creates Finding records from SSLScan output
- `ingest_httpx_findings()`: Creates Finding records from HTTPx output
- `ingest_ffuf_findings()`: Creates Finding records from FFuF output
- `ingest_dalfox_findings()`: Creates Finding records from Dalfox output
- `ingest_sqlmap_findings()`: Creates Finding records from SQLMap output
- `ingest_http_header_findings()`: Creates Finding records from HTTP header checks

### Normalization Rules

**Severity Mapping:**
- Tool-specific severities → enum (critical, high, medium, low, info)
- Nuclei: `critical`, `high`, `medium`, `low`, `info` → direct mapping
- Nmap: Service detection → `info`, vulnerabilities → `medium`/`high`
- SSLScan: Certificate issues → `high`, weak ciphers → `medium`

**CVE Extraction:**
- Nuclei: `info.classification.cve-id` → `finding.cve_id`
- Other tools: Extracted from descriptions/tags

**Category Tagging:**
- Nuclei tags mapped via `NUCLEI_TAG_TO_CATEGORY`:
  - `"xss"` → `"xss"`
  - `"sqli"` → `"sqli"`
  - `"lfi"`, `"rfi"` → `"dir_traversal"`
  - Stored in `raw_data.categories` array

**URL Normalization:**
- Base URL from project + path from finding
- Stored in `finding.url`

**CVSS Score:**
- Extracted from Nuclei: `info.classification.cvss-score` → `finding.cvss_score`

### Finding Model (`backend/app/models/finding.py`)

**Fields:**
- `id` (UUID string, PK)
- `scan_job_id` (FK → scan_jobs)
- `title` (String, 500 chars)
- `description` (Text)
- `severity` (Enum: critical, high, medium, low, info)
- `cve_id` (String, nullable, indexed)
- `cwe_id` (String, nullable)
- `cvss_score` (Float, nullable)
- `url` (String, 2048 chars, nullable)
- `path` (String, 2048 chars, nullable)
- `line_number` (Integer, nullable)
- `recommendation` (Text, nullable)
- `tool_name` (String, 100 chars, nullable, indexed)
- `raw_data` (Text, nullable): JSON string of original tool output
- `status` (Enum: open, acknowledged, resolved, suppressed)
- `created_at` (DateTime)

### ToolResult Model (`backend/app/models/finding.py`)

**Fields:**
- `id` (UUID string, PK)
- `scan_job_id` (FK → scan_jobs)
- `tool_name` (String, 100 chars, indexed)
- `tool_version` (String, 50 chars, nullable)
- `output` (Text, nullable): Raw stdout/stderr (may be truncated)
- `exit_code` (Integer, nullable)
- `execution_time` (Float, nullable): Seconds
- `timed_out` (Integer, 0/1): Boolean flag
- `command` (Text, nullable): Exact command executed
- `error_message` (Text, nullable)
- `created_at` (DateTime)

## Frontend Report Rendering

### Expected JSON Structure

The frontend expects scan data from `/api/v1/scans/{scan_id}` in `ScanResponse` format:

```typescript
{
  id: string;
  project_id: string;
  scan_level: "basic" | "pro" | "advanced";
  status: "pending" | "queued" | "running" | "completed" | "failed" | "cancelled";
  summary?: {
    risk_score?: number;
    findings_count?: number;
    executive_summary?: string;
    top_risks?: string[];
    remediation_overview?: string;
    severity_breakdown?: Record<string, number>;
  };
  stack_info?: {
    target_url?: string;
    scan_level?: string;
    http?: {
      status_code?: number;
      headers?: Record<string, string>;
    };
  };
  ai_plan?: {
    next_tools?: Array<{key: string, mode: string, ...}>;
    attack_paths?: Array<...>;
    reasoning?: string;
  };
  ai_status?: "idle" | "planned" | "failed";
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  findings: Array<{
    id: string;
    title: string;
    description?: string;
    severity: "critical" | "high" | "medium" | "low" | "info";
    status: "open" | "acknowledged" | "resolved" | "suppressed";
    cve_id?: string;
    cwe_id?: string;
    cvss_score?: number;
    url?: string;
    path?: string;
    recommendation?: string;
    tool_name?: string;
    created_at: string;
  }>;
}
```

### Frontend Pages

1. **Scan List** (`/projects/[projectId]/scans`):
   - Lists all scans for a project
   - Shows status, risk score, findings count

2. **Scan Detail** (`/projects/[projectId]/scans/[scanId]`):
   - Full scan report with findings
   - Summary metrics, severity breakdown
   - Tool execution results
   - AI plan visualization

3. **Dashboard Reports** (`/dashboard/scan/report/[job_id]`):
   - Legacy report page
   - Shows vulnerabilities, security score, open ports

## What is an "Artifact" in This Codebase?

### Definition

An **artifact** is any output produced by a tool during scan execution.

### Types of Artifacts

1. **Tool Output Files**:
   - Location: `backend/data/jobs/{scan_job_id}/{tool_name}_output.json`
   - Format: Tool-specific (JSON, JSONL, XML converted to JSON)
   - Examples:
     - `nuclei_output.json`: JSONL of vulnerability findings
     - `nmap_output.json`: XML converted to JSON (ports, services)
     - `sslscan_output.json`: SSL/TLS scan results
     - `ffuf_output.json`: Directory brute-force results
     - `dalfox_output.json`: XSS scan results
     - `sqlmap_output.json`: SQL injection scan results

2. **Database Records**:
   - `ToolResult`: Metadata about tool execution
     - `output`: Raw stdout/stderr (may be truncated for large outputs)
     - `command`: Exact command executed
     - `exit_code`, `execution_time`, `timed_out`
   - `Finding`: Normalized security findings
     - `raw_data`: Original tool output (JSON string)
     - Normalized fields: `title`, `severity`, `cve_id`, `url`, etc.

3. **Scan Metadata** (JSON fields in `scan_jobs`):
   - `stack_info`: Target HTTP metadata (headers, status_code)
   - `ai_plan`: AI-generated plan (next_tools, attack_paths)
   - `summary`: AI-generated report (risk_score, executive_summary, top_risks)

### Artifact Lifecycle

1. **Generation**: Tool execution produces output
2. **Storage**: 
   - File written to `data/jobs/{scan_job_id}/`
   - `ToolResult` record created in DB
3. **Parsing**: Tool-specific parser extracts structured data
4. **Normalization**: Parser output → `Finding` records
5. **Retrieval**: 
   - Frontend requests findings via `/api/v1/scans/{scan_id}/findings`
   - Artifact files can be accessed via file system (not exposed via API currently)

## Database Schema Summary

### Core Tables

- **`projects`**: Target projects (name, target_url, tenant_id)
- **`scan_jobs`**: Scan execution records (status, summary JSON, stack_info JSON, ai_plan JSON)
- **`findings`**: Normalized security findings (title, severity, cve_id, url, tool_name, raw_data JSON)
- **`tool_results`**: Raw tool execution metadata (output, command, exit_code, execution_time)
- **`tenants`**: Multi-tenant organizations (plan tiers, limits)
- **`users`**: User accounts (email, username, password hash)
- **`threat_item`**: CVE/threat intelligence data (for future use)

### Relationships

- `Project` → `ScanJob` (one-to-many)
- `ScanJob` → `Finding` (one-to-many)
- `ScanJob` → `ToolResult` (one-to-many)
- `Project` → `Tenant` (many-to-one)
- `User` → `Tenant` (many-to-one)

## Key Technologies

- **Backend**: FastAPI, SQLAlchemy, Alembic, Celery, Redis
- **Frontend**: Next.js, React, TypeScript, TailwindCSS
- **Database**: PostgreSQL (production), SQLite (development)
- **Task Queue**: Celery with Redis broker
- **Vector DB**: Qdrant (default) or PostgreSQL + pgvector
- **Embeddings**: Sentence Transformers (default) or OpenAI
- **AI**: OpenAI GPT-4o-mini for planning and reporting
