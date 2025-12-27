# Thandev Overview

## Purpose & Vision

Thandev is a comprehensive security intelligence platform that provides real-time vulnerability scanning, security news aggregation, exploit tracking, and performance analysis. It combines multiple security tools and data sources into a unified, modern interface designed for security professionals, developers, and organizations.

The platform enables users to:
- Scan web applications and infrastructure for security vulnerabilities
- Track and analyze CVE data and exploits
- Stay informed with aggregated security news
- Monitor application performance
- Generate comprehensive security reports

## High-Level Feature Set

### Security Scanning

Thandev provides multi-tier security scanning with three levels:

- **Basic**: Fast scans with essential tools (httpx, nuclei). Typically completes in 3-8 minutes.
- **Pro**: Comprehensive scans with additional tools (ffuf, nmap, sslscan, dalfox). Typically completes in 10-25 minutes.
- **Advanced**: Complete security scans with all available tools including SQL injection testing (sqlmap). Typically completes in 20-45 minutes.

**Supported Security Tools:**
- **httpx**: HTTP surface discovery
- **nuclei**: Vulnerability scanner with 1000+ templates
- **nmap**: Network port scanner and service detection
- **sslscan**: SSL/TLS configuration analysis
- **ffuf**: Web fuzzer for directory discovery
- **dalfox**: XSS (Cross-Site Scripting) scanner
- **sqlmap**: SQL injection testing

**Key Capabilities:**
- Real-time scan progress tracking
- Detailed vulnerability findings with severity classification
- Executive and full technical PDF reports
- Scan history and trend analysis
- AI-powered scan planning and report generation

### AI Brain Service

The Thandev Brain service provides RAG (Retrieval-Augmented Generation) powered intelligence:

- **Scan Planning**: Intelligently selects tools and execution modes based on target characteristics
- **Report Generation**: Builds comprehensive report prompts for AI-generated summaries
- **Finding Enrichment**: Enhances findings with impact summaries and remediation guidance

### Security News Aggregation

- Real-time RSS feed aggregation from certified security sources
- Source filtering and categorization
- Article content extraction and readability
- News statistics and trending topics

### Exploit Feed

- Real-time CVE data from NVD (National Vulnerability Database)
- EPSS (Exploit Prediction Scoring System) integration
- KEV (Known Exploited Vulnerabilities) tracking
- Advanced filtering by severity, CVE ID, date, and source

### Performance Scanning

- Google Lighthouse-powered performance analysis
- Core Web Vitals metrics (FCP, LCP, CLS, FID)
- Desktop and mobile device testing
- Optimization recommendations

## High-Level Module Map

Thandev is organized into several key subsystems:

### Backend (`backend/`)

FastAPI-based API server that handles:
- User authentication and authorization
- Project and scan management
- Scan orchestration and tool execution coordination
- Findings ingestion and lifecycle management
- PDF report generation
- API endpoints for frontend consumption

**Key Components:**
- `app/main.py`: FastAPI application entry point
- `app/api/`: REST API route handlers
- `app/models/`: SQLAlchemy database models
- `app/services/`: Business logic (scan orchestration, findings ingestion, PDF generation)
- `app/core/`: Core configuration, database, tenant utilities

### Brain Service (`services/thandev-brain/`)

Separate FastAPI service providing:
- RAG-powered scan planning
- Report prompt generation
- Finding enrichment (when enabled)

**Key Components:**
- `app/main.py`: Brain service entry point
- `app/api/v1.py`: API endpoints for planning and prompts
- `app/planner/`: Scan plan generation logic
- `app/report_prompt/`: Report prompt builder
- `app/rag/`: RAG storage and embedding providers

### Runner Service (`services/thandev-runner/`)

Tool execution service that:
- Consumes scan step requests from Redis streams
- Executes security tools (nuclei, nmap, etc.)
- Ingests findings into the database
- Publishes results back via Redis streams

**Key Components:**
- `app/main.py`: Runner service entry point
- `app/executor/`: Tool execution adapters
- `app/ingestor/`: Findings ingestion logic

### Frontend (`frontend/`)

Next.js 14 application providing:
- User interface for all platform features
- Dashboard and analytics
- Scan management and results visualization
- Security news and exploit browsing

**Key Components:**
- `app/`: Next.js App Router pages
- `components/`: React UI components
- `lib/`: Client-side utilities and API clients

### Cloud Run Services (`cloud-run/`)

Google Cloud Run job services for:
- Security scanning (legacy/alternative execution path)
- Performance scanning with Lighthouse

## End-to-End Happy Path

### 1. User Authentication

User signs in via GitHub OAuth:
- Frontend redirects to GitHub OAuth
- GitHub redirects back with authorization code
- Backend exchanges code for access token
- Session created with NextAuth.js
- User can now access authenticated endpoints

### 2. Project Creation

User creates a project:
- Frontend: User navigates to `/projects` and clicks "New Project"
- Frontend: POST `/api/projects` with `{name, target_url, description}`
- Backend: Creates `Project` record with `owner_id` and `tenant_id`
- Response: Project details with ID

### 3. Scan Execution

User runs a security scan:
- Frontend: User selects project and scan level (basic/pro/advanced)
- Frontend: POST `/api/scans` with `{project_id, scan_level}`
- Backend: Creates `ScanJob` record with status `pending`
- Backend: Calls Brain service to generate scan plan (if enabled)
- Backend: Queues scan job via Celery or Redis streams
- Backend: Returns scan ID and status

### 4. Scan Processing

Scan executes in background:
- Runner service (or Celery worker) picks up scan job
- For each tool in the plan:
  - Tool executor runs the CLI tool (nuclei, nmap, etc.)
  - Tool output is saved to files
  - Findings ingestor parses output and creates `Finding` records
- Scan status updated to `running` → `completed`
- Tool execution statuses tracked in `ToolResult` records

### 5. Results Viewing

User views scan results:
- Frontend: Polls GET `/api/scans/{scan_id}` for status updates
- When completed: Frontend fetches GET `/api/scans/{scan_id}/findings`
- Backend: Returns findings with location, impact, and remediation data
- Frontend: Displays findings in scan detail page with:
  - "Where it was found" (URL, method, parameter)
  - "What we found" (description)
  - "Why it matters" (impact summary)
  - "How to fix it" (remediation steps)

### 6. Report Generation

User downloads PDF report:
- Frontend: User clicks "Download Full PDF" or "Download Executive PDF"
- Frontend: GET `/api/scans/{scan_id}/report.pdf?mode=full` (or `executive`)
- Backend: Generates PDF using report templates and findings data
- Backend: Returns PDF as streaming response
- Frontend: Triggers browser download

## Current Limitations / "Coming Soon"

Based on code analysis:

### Implemented Features
- ✅ Multi-tier security scanning (basic/pro/advanced)
- ✅ AI-powered scan planning via Brain service
- ✅ Findings lifecycle management (first_seen, last_seen, deduplication)
- ✅ PDF report generation (full and executive)
- ✅ Multi-tenancy with tenant/user isolation
- ✅ GitHub OAuth authentication
- ✅ Real-time scan progress tracking
- ✅ Security news aggregation
- ✅ CVE/exploit feed

### Planned / Not Yet Fully Implemented

- **Finding Enrichment**: Brain service has endpoints for finding enrichment, but may not be fully integrated into scan pipeline
- **WebSocket Updates**: Frontend uses polling for scan status; WebSocket support may be planned
- **Advanced Notifications**: Notification system exists but may need expansion
- **Scheduled Scans**: No evidence of cron-based scheduled scanning in codebase
- **API Key Management**: User-facing API key generation/management not evident
- **Custom Watchlists**: No watchlist functionality found in codebase

## Regenerating Documentation PDFs

From the repo root:

```bash
cd docs
./export_docs_to_pdf.sh
```

This script uses `npx md-to-pdf` to convert all Markdown files in `docs/` to PDF format.

