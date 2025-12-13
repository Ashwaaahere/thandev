# Thandev News & Vulnerabilities Documentation

## Table of Contents
1. [Security News Page](#security-news-page)
2. [Vulnerabilities Page](#vulnerabilities-page)
3. [Scan Execution Flow](#scan-execution-flow)
4. [Architecture Overview](#architecture-overview)

---

## Security News Page

### Overview
The Security News page (`/news`) aggregates cybersecurity news from trusted RSS feeds, providing real-time threat intelligence to users. It's a public-facing page that doesn't require authentication.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   ├── news/
│   │   ├── page.tsx              # Server component (SEO metadata)
│   │   ├── NewsList.tsx          # News article list renderer
│   │   └── a/[id]/page.tsx       # Individual article detail page
│   └── api/
│       └── news/
│           └── route.ts          # Next.js API route (RSS aggregator)
└── components/
    └── News/
        ├── NewsPageClient.tsx    # Main client wrapper
        ├── NewsClientWrapper.tsx # Data fetching & pagination
        ├── NewsStats.tsx         # Statistics display
        ├── NewsList.tsx          # Article list component
        ├── LoadMoreButton.tsx    # Pagination control
        ├── RightSidebar.tsx      # Sidebar with pinned/latest
        ├── TopSourcesBox.tsx     # Source breakdown
        └── QuickFiltersBox.tsx  # Category filters
```

#### **Data Flow**

```
User Request → /news
    ↓
NewsPageClient (Client Component)
    ↓
NewsClientWrapper
    ↓
GET /api/news?category=cyber&limit=100
    ↓
Next.js API Route (route.ts)
    ↓
RSS Parser (rss-parser library)
    ↓
Fetch from multiple RSS sources (parallel)
    ↓
Normalize & deduplicate
    ↓
Filter by date, category, search
    ↓
Return JSON: { items: [], total: number }
    ↓
Render NewsList component
```

### RSS Sources

All sources are **certified** and fetched via HTTPS. The system aggregates from:

| Source | RSS URL | Category | Certified |
|--------|---------|----------|-----------|
| The Hacker News | `https://feeds.feedburner.com/TheHackersNews` | cyber | ✅ |
| BleepingComputer | `https://www.bleepingcomputer.com/feed/` | cyber | ✅ |
| Krebs on Security | `https://krebsonsecurity.com/feed/` | cyber | ✅ |
| SANS ISC Diary | `https://isc.sans.edu/rssfeed.xml` | cyber | ✅ |
| ZDI (Zero Day Initiative) | `https://www.zerodayinitiative.com/blog?format=rss` | cyber | ✅ |
| Dark Reading | `https://www.darkreading.com/rss.xml` | cyber | ✅ |
| Ars Technica Security | `https://arstechnica.com/security/feed/` | tech | ✅ |

**Location**: `frontend/app/api/news/route.ts:26-37`

### API Endpoint

**Route**: `GET /api/news`

**Query Parameters**:
- `category` (optional): Filter by category (`'cyber' | 'ai' | 'tech'`)
- `sinceDays` (optional, default: `21`): Only return articles from last N days
- `limit` (optional, default: `60`): Maximum number of articles to return
- `certifiedOnly` (optional, default: `'1'`): Only return certified sources (`'1'` or `'0'`)
- `q` (optional): Search query (searches in title, summary, source)

**Response**:
```typescript
{
  items: FeedItem[];
  total: number;
  sources_checked: number;
}

type FeedItem = {
  id: string;              // Format: "Source:URL"
  title: string;
  url: string;
  source: string;
  publishedAt: string;     // ISO 8601
  summary: string;        // Plain text, max 260 chars
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;  // HTTPS image URL or null
  certified: boolean;
}
```

**Location**: `frontend/app/api/news/route.ts:203-262`

### Image Extraction

The system attempts to extract images from RSS feeds using multiple strategies:

1. **RSS Standard Fields**: `enclosure.url`, `media:content`, `media:thumbnail`
2. **HTML Content Parsing**: Extracts `<img>` tags from `content:encoded`
3. **Article Page Fetching** (for specific sources):
   - Only for first 2 articles per source (performance optimization)
   - Sources: BleepingComputer, Krebs on Security, SANS ISC Diary
   - Fetches full HTML and extracts article images
   - Filters out logos, avatars, thumbnails
   - Prefers high-quality article images

**Security**: Only HTTPS images are allowed. Invalid URLs are filtered out.

**Location**: `frontend/app/api/news/route.ts:66-177`

### Data Processing Pipeline

1. **Fetch Phase** (Parallel):
   - All RSS sources are fetched concurrently using `Promise.all()`
   - Each source has a 15-second timeout
   - Failed sources are logged but don't block others

2. **Normalization Phase**:
   - Each RSS item is normalized to `FeedItem` format
   - Extracts: title, URL, published date, summary, image
   - Generates unique ID: `"Source:URL"`

3. **Deduplication Phase**:
   - Uses a `Map<string, FeedItem>` keyed by URL
   - Prevents duplicate articles from different sources

4. **Filtering Phase**:
   - Filters by date (`isRecent()` checks `publishedAt >= sinceMs`)
   - Filters by category (if specified)
   - Filters by certification status (if `certifiedOnly=true`)
   - Filters by search query (title, summary, source)

5. **Sorting Phase**:
   - Sorted by `publishedAt` descending (newest first)

**Location**: `frontend/app/api/news/route.ts:212-250`

### Frontend Components

#### **NewsPageClient** (`components/News/NewsPageClient.tsx`)
- Main client component wrapper
- Manages news state and statistics
- Renders stats bar and main feed layout
- Passes data to `NewsClientWrapper`

#### **NewsClientWrapper** (`components/News/NewsClientWrapper.tsx`)
- Handles data fetching and pagination
- Initial load: fetches first 31 articles
- Load more: fetches next 20 articles
- Manages loading states
- Calls `onStatsUpdate` callback for parent

#### **NewsList** (`app/news/NewsList.tsx`)
- Renders the article list
- Each article shows:
  - Image (if available)
  - Title (link to article)
  - Source badge
  - Published date
  - Summary excerpt
  - Category tag

#### **RightSidebar** (`components/News/RightSidebar.tsx`)
- Displays pinned articles (top 5)
- Shows latest articles
- Source statistics

### Performance Optimizations

1. **Timeout Protection**: 15-second timeout per RSS source
2. **Image Fetching**: Only first 2 articles per source fetch full HTML
3. **Pagination**: Initial load shows 31 articles, load more adds 20
4. **Caching**: Next.js API route uses `force-dynamic` (no caching for real-time data)
5. **Error Handling**: Failed sources don't block the entire feed

---

## Vulnerabilities Page

### Overview
The Vulnerabilities page (`/dashboard/vulnerabilities`) provides a centralized view of all security findings across a user's projects. It supports filtering, searching, and status management.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   └── dashboard/
│       └── vulnerabilities/
│           └── page.tsx           # Server component (auth check)
└── components/
    └── Dashboard/
        └── VulnerabilitiesClient.tsx  # Main client component
```

#### **Backend Structure**

```
backend/
├── app/
│   ├── api/
│   │   └── findings.py            # Findings API endpoints
│   ├── models/
│   │   └── finding.py            # Finding model
│   └── schemas/
│       └── finding.py             # Pydantic schemas
```

### Data Flow

```
User Request → /dashboard/vulnerabilities
    ↓
Server Component (page.tsx)
    ↓
Check NextAuth session
    ↓
VulnerabilitiesClient (Client Component)
    ↓
useSession() → Get session
    ↓
Load Projects (for filter dropdown)
    ↓
GET /api/projects
    ↓
Load Findings (with filters)
    ↓
GET /api/findings?severity=high&status=open&search=...
    ↓
Backend API (findings.py)
    ↓
SQLAlchemy Query (with tenant/user filtering)
    ↓
Return FindingListItem[]
    ↓
Render table with filters
```

### API Endpoints

#### **GET /api/findings**

Lists findings for the current tenant and user.

**Query Parameters**:
- `severity` (optional): Filter by severity (`critical`, `high`, `medium`, `low`, `info`)
- `status` (optional): Filter by status (`open`, `acknowledged`, `resolved`, `suppressed`)
- `tool` (optional): Filter by tool (`nuclei`, `nmap`, `sslscan`)
- `project_id` (optional): Filter by project ID
- `search` (optional): Search in title, description, CVE ID, CWE ID, URL, path
- `limit` (optional, default: `20`): Maximum results per page
- `offset` (optional, default: `0`): Pagination offset

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Response**:
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
  severity: string;           // "critical" | "high" | "medium" | "low" | "info"
  title: string;
  description?: string;
  cve_id?: string;
  cwe_id?: string;
  cvss_score?: number;
  tool: string;               // "nuclei" | "nmap" | "sslscan"
  url?: string;
  path?: string;
  status: string;            // "open" | "acknowledged" | "resolved" | "suppressed"
  first_seen: string;         // ISO 8601
  last_seen: string;         // ISO 8601
}
```

**Location**: `backend/app/api/findings.py:23-138`

#### **PATCH /api/findings/{finding_id}/status**

Updates the workflow status of a finding.

**Request Body**:
```json
{
  "status": "acknowledged"  // "open" | "acknowledged" | "resolved" | "suppressed"
}
```

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Authorization**: Ensures finding belongs to current tenant and user

**Response**: Updated `FindingListItem`

**Location**: `backend/app/api/findings.py:141-213`

### Database Query Structure

The findings query uses SQLAlchemy joins to ensure tenant/user isolation:

```python
query = (
    db.query(Finding, ScanJob, Project)
    .join(ScanJob, Finding.scan_job_id == ScanJob.id)
    .join(Project, ScanJob.project_id == Project.id)
    .filter(
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    )
)
```

**Key Points**:
- Findings are scoped via `Project.tenant_id` and `Project.owner_id`
- Results ordered by `Finding.created_at DESC` (newest first)
- Supports filtering by severity, status, tool, project, and search

**Location**: `backend/app/api/findings.py:49-111`

### Frontend Component

#### **VulnerabilitiesClient** (`components/Dashboard/VulnerabilitiesClient.tsx`)

**State Management**:
- `findings`: Array of findings to display
- `projects`: Array of projects (for filter dropdown)
- `severity`: Selected severity filter
- `selectedStatus`: Selected status filter
- `selectedTool`: Selected tool filter
- `search`: Search query (synced with URL)
- `projectId`: Selected project filter
- `page`: Current page number (pagination)
- `isLoading`: Loading state
- `error`: Error message
- `updatingStatus`: Finding ID being updated (for optimistic UI)

**Features**:
1. **Filtering**:
   - Severity dropdown (Critical, High, Medium, Low, Info)
   - Status dropdown (All, Open, Acknowledged, Resolved, Suppressed)
   - Tool dropdown (All, Nuclei, Nmap, SSLScan)
   - Project dropdown (All projects or specific project)
   - Search input (debounced, 300ms)

2. **URL Sync**:
   - Search query is synced with URL parameter `?search=...`
   - Supports global search integration

3. **Status Updates**:
   - Click status badge to change workflow status
   - Optimistic UI update
   - Calls `PATCH /api/findings/{id}/status`
   - Refetches on success

4. **Navigation**:
   - Project name links to `/projects/{projectId}`
   - "View scan" link to `/projects/{projectId}/scans/{scanId}`

5. **Pagination**:
   - Shows 20 findings per page
   - Previous/Next buttons
   - Displays total count

**Location**: `frontend/components/Dashboard/VulnerabilitiesClient.tsx`

### Security & Multi-Tenancy

- **Tenant Isolation**: All queries filter by `Project.tenant_id`
- **User Isolation**: All queries filter by `Project.owner_id`
- **Authorization**: Status updates verify ownership before allowing changes
- **Headers**: Uses `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication

---

## Scan Execution Flow

### Overview
The scan execution flow handles security scans from API request to completion, using Celery for background task processing.

### Architecture

```
Frontend Request
    ↓
FastAPI Endpoint (/api/scans or /api/scans/quick)
    ↓
Create ScanJob (status: PENDING)
    ↓
ScanOrchestrator.queue_scan()
    ↓
Celery Task (run_scan_task)
    ↓
run_scan_for_job()
    ↓
Scan Profiles (get scan level config)
    ↓
Tool Execution (Nuclei, Nmap, SSLScan)
    ↓
Parse Findings
    ↓
AI Report Generation
    ↓
Update ScanJob (status: COMPLETED)
    ↓
Store Findings in Database
```

### Detailed Flow

#### **Step 1: API Request**

**Endpoints**:
- `POST /api/scans` - Create scan for existing project
- `POST /api/scans/quick` - Quick scan (creates project if needed)

**Request Body** (`POST /api/scans`):
```json
{
  "project_id": "uuid",
  "scan_level": "pro"  // "basic" | "pro" | "advanced"
}
```

**Request Body** (`POST /api/scans/quick`):
```json
{
  "project_id": "uuid",        // Optional
  "target_url": "https://...", // Optional (required if no project_id)
  "scan_level": "pro"
}
```

**Location**: `backend/app/api/scans.py:209-363` and `366-530`

#### **Step 2: Validation & Project Resolution**

1. **Tenant/User Validation**:
   - Validates `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers
   - Ensures project belongs to tenant and user

2. **Plan Limits Check**:
   - Checks monthly scan quota
   - Checks concurrent scan limit
   - Validates scan level is allowed for plan

3. **Project Resolution** (for quick scan):
   - If `project_id` provided: Use existing project
   - If `target_url` provided: Find or create project

**Location**: `backend/app/api/scans.py:234-453`

#### **Step 3: ScanJob Creation**

Creates a `ScanJob` record in the database:

```python
scan_job = ScanJob(
    id=str(uuid.uuid4()),
    project_id=project.id,
    scan_level=ScanLevel(scan_level),
    status=ScanStatus.PENDING,
    tenant_id=tenant.id,
    owner_id=current_user.id,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/api/scans.py:290-315`

#### **Step 4: Celery Task Queueing**

Uses `ScanOrchestrator` to queue the scan:

```python
orchestrator = ScanOrchestrator()
celery_task_id = await orchestrator.queue_scan(
    scan_job.id,
    project.target_url,
    scan_level_str
)
```

**Location**: `backend/app/services/scan_orchestrator.py:19-46`

#### **Step 5: Celery Task Execution**

The Celery worker picks up the task:

```python
@celery.task(name="thandev.run_scan_task")
def run_scan_task(scan_job_id: str, target_url: str, scan_level: str):
    # Update status to RUNNING
    scan_job.status = ScanStatus.RUNNING
    scan_job.started_at = datetime.utcnow()
    
    # Run the scan
    run_scan_for_job(scan_job)
    
    # Update status to COMPLETED/FAILED
    scan_job.status = ScanStatus.COMPLETED
    scan_job.completed_at = datetime.utcnow()
```

**Location**: `backend/app/tasks/celery_app.py:26-96`

#### **Step 6: Scan Execution**

The `run_scan_for_job()` function orchestrates the scan:

1. **Get Scan Profile**:
   - Retrieves tool configuration for scan level
   - Basic: Lightweight tools
   - Pro: Standard tools
   - Advanced: Full tool suite

2. **Run Tools Sequentially**:
   - For each tool in profile:
     - Execute tool via `ToolExecutor.run_tool()`
     - Save output to `data/jobs/{job_id}/{tool}_output.json`
     - Parse findings from output
     - Create `Finding` records in database

3. **AI Report Generation**:
   - Generates executive summary
   - Identifies top risks
   - Calculates risk score
   - Creates remediation overview
   - Stores in `ScanJob.summary` (JSONB)

**Location**: `backend/app/services/scan_orchestrator.py:84-530`

#### **Step 7: Finding Storage**

Findings are stored in the `findings` table:

```python
finding = Finding(
    id=str(uuid.uuid4()),
    scan_job_id=scan_job.id,
    title=parsed_title,
    description=parsed_description,
    severity=Severity(severity),
    status=FindingStatus.OPEN,
    cve_id=cve_id,
    cwe_id=cwe_id,
    cvss_score=cvss_score,
    tool_name=tool_name,
    url=target_url,
    path=file_path,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/services/scan_orchestrator.py:300-450`

### Scan Levels & Tools

| Level | Tools | Description |
|-------|-------|-------------|
| **Basic** | Nuclei (light templates) | Fast surface scan, common vulnerabilities |
| **Pro** | Nuclei (full), Nmap, SSLScan | Deeper coverage, port scanning, TLS analysis |
| **Advanced** | All tools + extended templates | Full-stack probes, comprehensive analysis |

**Location**: `backend/app/services/scan_profiles.py`

### Status Lifecycle

```
PENDING → QUEUED → RUNNING → COMPLETED
                              ↓
                           FAILED (on error)
```

- **PENDING**: ScanJob created, not yet queued
- **QUEUED**: Celery task queued, waiting for worker
- **RUNNING**: Scan in progress
- **COMPLETED**: Scan finished successfully
- **FAILED**: Scan encountered an error

**Location**: `backend/app/models/scan.py:27-34`

### Error Handling

1. **Celery Queue Failure**:
   - Marks scan as `FAILED`
   - Stores error message in `error_message`
   - Returns HTTP 500 with details

2. **Tool Execution Failure**:
   - Logs error
   - Continues with other tools
   - Marks scan as `FAILED` if critical tool fails

3. **Database Errors**:
   - Rolls back transaction
   - Logs error with traceback
   - Returns appropriate HTTP status

**Location**: `backend/app/api/scans.py:331-345` and `backend/app/tasks/celery_app.py:95-120`

### Data Models

#### **ScanJob** (`backend/app/models/scan.py`)
- `id`: UUID
- `project_id`: Foreign key to Project
- `scan_level`: Enum (BASIC, PRO, ADVANCED)
- `status`: Enum (PENDING, QUEUED, RUNNING, COMPLETED, FAILED)
- `summary`: JSONB (AI-generated report)
- `stack_info`: JSONB (stack fingerprinting data)
- `celery_task_id`: Celery task identifier
- `created_at`, `started_at`, `completed_at`: Timestamps

#### **Finding** (`backend/app/models/finding.py`)
- `id`: UUID
- `scan_job_id`: Foreign key to ScanJob
- `title`: Finding title
- `description`: Detailed description
- `severity`: Enum (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- `status`: Enum (OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED)
- `cve_id`, `cwe_id`: Vulnerability identifiers
- `cvss_score`: CVSS score (0.0-10.0)
- `tool_name`: Tool that found it
- `url`, `path`: Location of vulnerability

---

## Architecture Overview

### Technology Stack

**Frontend**:
- Next.js 14 (App Router)
- React 18
- TypeScript
- NextAuth (authentication)
- Tailwind CSS

**Backend**:
- FastAPI
- SQLAlchemy (ORM)
- Celery (task queue)
- PostgreSQL/SQLite (database)
- Pydantic (validation)

**Tools**:
- Nuclei (vulnerability scanner)
- Nmap (port scanner)
- SSLScan (TLS analyzer)

### Multi-Tenancy

- **Tenant Model**: Each user has a tenant (1:1 mapping currently)
- **Isolation**: All queries filter by `Project.tenant_id` and `Project.owner_id`
- **Headers**: `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication
- **Future**: Support for org accounts with multiple users per tenant

### Security Considerations

1. **Authentication**: NextAuth session required for dashboard pages
2. **Authorization**: All API endpoints verify tenant/user ownership
3. **Input Validation**: Pydantic schemas validate all inputs
4. **SQL Injection**: SQLAlchemy ORM prevents SQL injection
5. **Rate Limiting**: Plan-based limits on scans per month
6. **HTTPS Only**: RSS images must be HTTPS

### Performance Optimizations

1. **Parallel RSS Fetching**: All news sources fetched concurrently
2. **Pagination**: Findings and news use pagination
3. **Debouncing**: Search inputs debounced (300ms)
4. **Lazy Loading**: Images loaded lazily
5. **Background Tasks**: Scans run in Celery workers
6. **Database Indexing**: Foreign keys and common filters indexed

---

## File Reference

### News System
- `frontend/app/api/news/route.ts` - RSS aggregation API
- `frontend/app/news/page.tsx` - News page server component
- `frontend/components/News/NewsPageClient.tsx` - Main client component
- `frontend/components/News/NewsClientWrapper.tsx` - Data fetching wrapper

### Vulnerabilities System
- `backend/app/api/findings.py` - Findings API endpoints
- `frontend/components/Dashboard/VulnerabilitiesClient.tsx` - Vulnerabilities UI
- `backend/app/models/finding.py` - Finding database model
- `backend/app/schemas/finding.py` - Pydantic schemas

### Scan System
- `backend/app/api/scans.py` - Scan API endpoints
- `backend/app/services/scan_orchestrator.py` - Scan orchestration
- `backend/app/tasks/celery_app.py` - Celery task definitions
- `backend/app/services/scan_profiles.py` - Scan level configurations
- `backend/app/services/tools.py` - Tool execution

---

## Summary

This documentation covers:
1. **News Page**: RSS aggregation from 7 certified sources, real-time updates, image extraction
2. **Vulnerabilities Page**: Centralized findings view with filtering, search, and status management
3. **Scan Flow**: End-to-end scan execution from API to Celery to database storage

All systems are multi-tenant, secure, and optimized for performance.





## Table of Contents
1. [Security News Page](#security-news-page)
2. [Vulnerabilities Page](#vulnerabilities-page)
3. [Scan Execution Flow](#scan-execution-flow)
4. [Architecture Overview](#architecture-overview)

---

## Security News Page

### Overview
The Security News page (`/news`) aggregates cybersecurity news from trusted RSS feeds, providing real-time threat intelligence to users. It's a public-facing page that doesn't require authentication.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   ├── news/
│   │   ├── page.tsx              # Server component (SEO metadata)
│   │   ├── NewsList.tsx          # News article list renderer
│   │   └── a/[id]/page.tsx       # Individual article detail page
│   └── api/
│       └── news/
│           └── route.ts          # Next.js API route (RSS aggregator)
└── components/
    └── News/
        ├── NewsPageClient.tsx    # Main client wrapper
        ├── NewsClientWrapper.tsx # Data fetching & pagination
        ├── NewsStats.tsx         # Statistics display
        ├── NewsList.tsx          # Article list component
        ├── LoadMoreButton.tsx    # Pagination control
        ├── RightSidebar.tsx      # Sidebar with pinned/latest
        ├── TopSourcesBox.tsx     # Source breakdown
        └── QuickFiltersBox.tsx  # Category filters
```

#### **Data Flow**

```
User Request → /news
    ↓
NewsPageClient (Client Component)
    ↓
NewsClientWrapper
    ↓
GET /api/news?category=cyber&limit=100
    ↓
Next.js API Route (route.ts)
    ↓
RSS Parser (rss-parser library)
    ↓
Fetch from multiple RSS sources (parallel)
    ↓
Normalize & deduplicate
    ↓
Filter by date, category, search
    ↓
Return JSON: { items: [], total: number }
    ↓
Render NewsList component
```

### RSS Sources

All sources are **certified** and fetched via HTTPS. The system aggregates from:

| Source | RSS URL | Category | Certified |
|--------|---------|----------|-----------|
| The Hacker News | `https://feeds.feedburner.com/TheHackersNews` | cyber | ✅ |
| BleepingComputer | `https://www.bleepingcomputer.com/feed/` | cyber | ✅ |
| Krebs on Security | `https://krebsonsecurity.com/feed/` | cyber | ✅ |
| SANS ISC Diary | `https://isc.sans.edu/rssfeed.xml` | cyber | ✅ |
| ZDI (Zero Day Initiative) | `https://www.zerodayinitiative.com/blog?format=rss` | cyber | ✅ |
| Dark Reading | `https://www.darkreading.com/rss.xml` | cyber | ✅ |
| Ars Technica Security | `https://arstechnica.com/security/feed/` | tech | ✅ |

**Location**: `frontend/app/api/news/route.ts:26-37`

### API Endpoint

**Route**: `GET /api/news`

**Query Parameters**:
- `category` (optional): Filter by category (`'cyber' | 'ai' | 'tech'`)
- `sinceDays` (optional, default: `21`): Only return articles from last N days
- `limit` (optional, default: `60`): Maximum number of articles to return
- `certifiedOnly` (optional, default: `'1'`): Only return certified sources (`'1'` or `'0'`)
- `q` (optional): Search query (searches in title, summary, source)

**Response**:
```typescript
{
  items: FeedItem[];
  total: number;
  sources_checked: number;
}

type FeedItem = {
  id: string;              // Format: "Source:URL"
  title: string;
  url: string;
  source: string;
  publishedAt: string;     // ISO 8601
  summary: string;        // Plain text, max 260 chars
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;  // HTTPS image URL or null
  certified: boolean;
}
```

**Location**: `frontend/app/api/news/route.ts:203-262`

### Image Extraction

The system attempts to extract images from RSS feeds using multiple strategies:

1. **RSS Standard Fields**: `enclosure.url`, `media:content`, `media:thumbnail`
2. **HTML Content Parsing**: Extracts `<img>` tags from `content:encoded`
3. **Article Page Fetching** (for specific sources):
   - Only for first 2 articles per source (performance optimization)
   - Sources: BleepingComputer, Krebs on Security, SANS ISC Diary
   - Fetches full HTML and extracts article images
   - Filters out logos, avatars, thumbnails
   - Prefers high-quality article images

**Security**: Only HTTPS images are allowed. Invalid URLs are filtered out.

**Location**: `frontend/app/api/news/route.ts:66-177`

### Data Processing Pipeline

1. **Fetch Phase** (Parallel):
   - All RSS sources are fetched concurrently using `Promise.all()`
   - Each source has a 15-second timeout
   - Failed sources are logged but don't block others

2. **Normalization Phase**:
   - Each RSS item is normalized to `FeedItem` format
   - Extracts: title, URL, published date, summary, image
   - Generates unique ID: `"Source:URL"`

3. **Deduplication Phase**:
   - Uses a `Map<string, FeedItem>` keyed by URL
   - Prevents duplicate articles from different sources

4. **Filtering Phase**:
   - Filters by date (`isRecent()` checks `publishedAt >= sinceMs`)
   - Filters by category (if specified)
   - Filters by certification status (if `certifiedOnly=true`)
   - Filters by search query (title, summary, source)

5. **Sorting Phase**:
   - Sorted by `publishedAt` descending (newest first)

**Location**: `frontend/app/api/news/route.ts:212-250`

### Frontend Components

#### **NewsPageClient** (`components/News/NewsPageClient.tsx`)
- Main client component wrapper
- Manages news state and statistics
- Renders stats bar and main feed layout
- Passes data to `NewsClientWrapper`

#### **NewsClientWrapper** (`components/News/NewsClientWrapper.tsx`)
- Handles data fetching and pagination
- Initial load: fetches first 31 articles
- Load more: fetches next 20 articles
- Manages loading states
- Calls `onStatsUpdate` callback for parent

#### **NewsList** (`app/news/NewsList.tsx`)
- Renders the article list
- Each article shows:
  - Image (if available)
  - Title (link to article)
  - Source badge
  - Published date
  - Summary excerpt
  - Category tag

#### **RightSidebar** (`components/News/RightSidebar.tsx`)
- Displays pinned articles (top 5)
- Shows latest articles
- Source statistics

### Performance Optimizations

1. **Timeout Protection**: 15-second timeout per RSS source
2. **Image Fetching**: Only first 2 articles per source fetch full HTML
3. **Pagination**: Initial load shows 31 articles, load more adds 20
4. **Caching**: Next.js API route uses `force-dynamic` (no caching for real-time data)
5. **Error Handling**: Failed sources don't block the entire feed

---

## Vulnerabilities Page

### Overview
The Vulnerabilities page (`/dashboard/vulnerabilities`) provides a centralized view of all security findings across a user's projects. It supports filtering, searching, and status management.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   └── dashboard/
│       └── vulnerabilities/
│           └── page.tsx           # Server component (auth check)
└── components/
    └── Dashboard/
        └── VulnerabilitiesClient.tsx  # Main client component
```

#### **Backend Structure**

```
backend/
├── app/
│   ├── api/
│   │   └── findings.py            # Findings API endpoints
│   ├── models/
│   │   └── finding.py            # Finding model
│   └── schemas/
│       └── finding.py             # Pydantic schemas
```

### Data Flow

```
User Request → /dashboard/vulnerabilities
    ↓
Server Component (page.tsx)
    ↓
Check NextAuth session
    ↓
VulnerabilitiesClient (Client Component)
    ↓
useSession() → Get session
    ↓
Load Projects (for filter dropdown)
    ↓
GET /api/projects
    ↓
Load Findings (with filters)
    ↓
GET /api/findings?severity=high&status=open&search=...
    ↓
Backend API (findings.py)
    ↓
SQLAlchemy Query (with tenant/user filtering)
    ↓
Return FindingListItem[]
    ↓
Render table with filters
```

### API Endpoints

#### **GET /api/findings**

Lists findings for the current tenant and user.

**Query Parameters**:
- `severity` (optional): Filter by severity (`critical`, `high`, `medium`, `low`, `info`)
- `status` (optional): Filter by status (`open`, `acknowledged`, `resolved`, `suppressed`)
- `tool` (optional): Filter by tool (`nuclei`, `nmap`, `sslscan`)
- `project_id` (optional): Filter by project ID
- `search` (optional): Search in title, description, CVE ID, CWE ID, URL, path
- `limit` (optional, default: `20`): Maximum results per page
- `offset` (optional, default: `0`): Pagination offset

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Response**:
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
  severity: string;           // "critical" | "high" | "medium" | "low" | "info"
  title: string;
  description?: string;
  cve_id?: string;
  cwe_id?: string;
  cvss_score?: number;
  tool: string;               // "nuclei" | "nmap" | "sslscan"
  url?: string;
  path?: string;
  status: string;            // "open" | "acknowledged" | "resolved" | "suppressed"
  first_seen: string;         // ISO 8601
  last_seen: string;         // ISO 8601
}
```

**Location**: `backend/app/api/findings.py:23-138`

#### **PATCH /api/findings/{finding_id}/status**

Updates the workflow status of a finding.

**Request Body**:
```json
{
  "status": "acknowledged"  // "open" | "acknowledged" | "resolved" | "suppressed"
}
```

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Authorization**: Ensures finding belongs to current tenant and user

**Response**: Updated `FindingListItem`

**Location**: `backend/app/api/findings.py:141-213`

### Database Query Structure

The findings query uses SQLAlchemy joins to ensure tenant/user isolation:

```python
query = (
    db.query(Finding, ScanJob, Project)
    .join(ScanJob, Finding.scan_job_id == ScanJob.id)
    .join(Project, ScanJob.project_id == Project.id)
    .filter(
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    )
)
```

**Key Points**:
- Findings are scoped via `Project.tenant_id` and `Project.owner_id`
- Results ordered by `Finding.created_at DESC` (newest first)
- Supports filtering by severity, status, tool, project, and search

**Location**: `backend/app/api/findings.py:49-111`

### Frontend Component

#### **VulnerabilitiesClient** (`components/Dashboard/VulnerabilitiesClient.tsx`)

**State Management**:
- `findings`: Array of findings to display
- `projects`: Array of projects (for filter dropdown)
- `severity`: Selected severity filter
- `selectedStatus`: Selected status filter
- `selectedTool`: Selected tool filter
- `search`: Search query (synced with URL)
- `projectId`: Selected project filter
- `page`: Current page number (pagination)
- `isLoading`: Loading state
- `error`: Error message
- `updatingStatus`: Finding ID being updated (for optimistic UI)

**Features**:
1. **Filtering**:
   - Severity dropdown (Critical, High, Medium, Low, Info)
   - Status dropdown (All, Open, Acknowledged, Resolved, Suppressed)
   - Tool dropdown (All, Nuclei, Nmap, SSLScan)
   - Project dropdown (All projects or specific project)
   - Search input (debounced, 300ms)

2. **URL Sync**:
   - Search query is synced with URL parameter `?search=...`
   - Supports global search integration

3. **Status Updates**:
   - Click status badge to change workflow status
   - Optimistic UI update
   - Calls `PATCH /api/findings/{id}/status`
   - Refetches on success

4. **Navigation**:
   - Project name links to `/projects/{projectId}`
   - "View scan" link to `/projects/{projectId}/scans/{scanId}`

5. **Pagination**:
   - Shows 20 findings per page
   - Previous/Next buttons
   - Displays total count

**Location**: `frontend/components/Dashboard/VulnerabilitiesClient.tsx`

### Security & Multi-Tenancy

- **Tenant Isolation**: All queries filter by `Project.tenant_id`
- **User Isolation**: All queries filter by `Project.owner_id`
- **Authorization**: Status updates verify ownership before allowing changes
- **Headers**: Uses `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication

---

## Scan Execution Flow

### Overview
The scan execution flow handles security scans from API request to completion, using Celery for background task processing.

### Architecture

```
Frontend Request
    ↓
FastAPI Endpoint (/api/scans or /api/scans/quick)
    ↓
Create ScanJob (status: PENDING)
    ↓
ScanOrchestrator.queue_scan()
    ↓
Celery Task (run_scan_task)
    ↓
run_scan_for_job()
    ↓
Scan Profiles (get scan level config)
    ↓
Tool Execution (Nuclei, Nmap, SSLScan)
    ↓
Parse Findings
    ↓
AI Report Generation
    ↓
Update ScanJob (status: COMPLETED)
    ↓
Store Findings in Database
```

### Detailed Flow

#### **Step 1: API Request**

**Endpoints**:
- `POST /api/scans` - Create scan for existing project
- `POST /api/scans/quick` - Quick scan (creates project if needed)

**Request Body** (`POST /api/scans`):
```json
{
  "project_id": "uuid",
  "scan_level": "pro"  // "basic" | "pro" | "advanced"
}
```

**Request Body** (`POST /api/scans/quick`):
```json
{
  "project_id": "uuid",        // Optional
  "target_url": "https://...", // Optional (required if no project_id)
  "scan_level": "pro"
}
```

**Location**: `backend/app/api/scans.py:209-363` and `366-530`

#### **Step 2: Validation & Project Resolution**

1. **Tenant/User Validation**:
   - Validates `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers
   - Ensures project belongs to tenant and user

2. **Plan Limits Check**:
   - Checks monthly scan quota
   - Checks concurrent scan limit
   - Validates scan level is allowed for plan

3. **Project Resolution** (for quick scan):
   - If `project_id` provided: Use existing project
   - If `target_url` provided: Find or create project

**Location**: `backend/app/api/scans.py:234-453`

#### **Step 3: ScanJob Creation**

Creates a `ScanJob` record in the database:

```python
scan_job = ScanJob(
    id=str(uuid.uuid4()),
    project_id=project.id,
    scan_level=ScanLevel(scan_level),
    status=ScanStatus.PENDING,
    tenant_id=tenant.id,
    owner_id=current_user.id,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/api/scans.py:290-315`

#### **Step 4: Celery Task Queueing**

Uses `ScanOrchestrator` to queue the scan:

```python
orchestrator = ScanOrchestrator()
celery_task_id = await orchestrator.queue_scan(
    scan_job.id,
    project.target_url,
    scan_level_str
)
```

**Location**: `backend/app/services/scan_orchestrator.py:19-46`

#### **Step 5: Celery Task Execution**

The Celery worker picks up the task:

```python
@celery.task(name="thandev.run_scan_task")
def run_scan_task(scan_job_id: str, target_url: str, scan_level: str):
    # Update status to RUNNING
    scan_job.status = ScanStatus.RUNNING
    scan_job.started_at = datetime.utcnow()
    
    # Run the scan
    run_scan_for_job(scan_job)
    
    # Update status to COMPLETED/FAILED
    scan_job.status = ScanStatus.COMPLETED
    scan_job.completed_at = datetime.utcnow()
```

**Location**: `backend/app/tasks/celery_app.py:26-96`

#### **Step 6: Scan Execution**

The `run_scan_for_job()` function orchestrates the scan:

1. **Get Scan Profile**:
   - Retrieves tool configuration for scan level
   - Basic: Lightweight tools
   - Pro: Standard tools
   - Advanced: Full tool suite

2. **Run Tools Sequentially**:
   - For each tool in profile:
     - Execute tool via `ToolExecutor.run_tool()`
     - Save output to `data/jobs/{job_id}/{tool}_output.json`
     - Parse findings from output
     - Create `Finding` records in database

3. **AI Report Generation**:
   - Generates executive summary
   - Identifies top risks
   - Calculates risk score
   - Creates remediation overview
   - Stores in `ScanJob.summary` (JSONB)

**Location**: `backend/app/services/scan_orchestrator.py:84-530`

#### **Step 7: Finding Storage**

Findings are stored in the `findings` table:

```python
finding = Finding(
    id=str(uuid.uuid4()),
    scan_job_id=scan_job.id,
    title=parsed_title,
    description=parsed_description,
    severity=Severity(severity),
    status=FindingStatus.OPEN,
    cve_id=cve_id,
    cwe_id=cwe_id,
    cvss_score=cvss_score,
    tool_name=tool_name,
    url=target_url,
    path=file_path,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/services/scan_orchestrator.py:300-450`

### Scan Levels & Tools

| Level | Tools | Description |
|-------|-------|-------------|
| **Basic** | Nuclei (light templates) | Fast surface scan, common vulnerabilities |
| **Pro** | Nuclei (full), Nmap, SSLScan | Deeper coverage, port scanning, TLS analysis |
| **Advanced** | All tools + extended templates | Full-stack probes, comprehensive analysis |

**Location**: `backend/app/services/scan_profiles.py`

### Status Lifecycle

```
PENDING → QUEUED → RUNNING → COMPLETED
                              ↓
                           FAILED (on error)
```

- **PENDING**: ScanJob created, not yet queued
- **QUEUED**: Celery task queued, waiting for worker
- **RUNNING**: Scan in progress
- **COMPLETED**: Scan finished successfully
- **FAILED**: Scan encountered an error

**Location**: `backend/app/models/scan.py:27-34`

### Error Handling

1. **Celery Queue Failure**:
   - Marks scan as `FAILED`
   - Stores error message in `error_message`
   - Returns HTTP 500 with details

2. **Tool Execution Failure**:
   - Logs error
   - Continues with other tools
   - Marks scan as `FAILED` if critical tool fails

3. **Database Errors**:
   - Rolls back transaction
   - Logs error with traceback
   - Returns appropriate HTTP status

**Location**: `backend/app/api/scans.py:331-345` and `backend/app/tasks/celery_app.py:95-120`

### Data Models

#### **ScanJob** (`backend/app/models/scan.py`)
- `id`: UUID
- `project_id`: Foreign key to Project
- `scan_level`: Enum (BASIC, PRO, ADVANCED)
- `status`: Enum (PENDING, QUEUED, RUNNING, COMPLETED, FAILED)
- `summary`: JSONB (AI-generated report)
- `stack_info`: JSONB (stack fingerprinting data)
- `celery_task_id`: Celery task identifier
- `created_at`, `started_at`, `completed_at`: Timestamps

#### **Finding** (`backend/app/models/finding.py`)
- `id`: UUID
- `scan_job_id`: Foreign key to ScanJob
- `title`: Finding title
- `description`: Detailed description
- `severity`: Enum (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- `status`: Enum (OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED)
- `cve_id`, `cwe_id`: Vulnerability identifiers
- `cvss_score`: CVSS score (0.0-10.0)
- `tool_name`: Tool that found it
- `url`, `path`: Location of vulnerability

---

## Architecture Overview

### Technology Stack

**Frontend**:
- Next.js 14 (App Router)
- React 18
- TypeScript
- NextAuth (authentication)
- Tailwind CSS

**Backend**:
- FastAPI
- SQLAlchemy (ORM)
- Celery (task queue)
- PostgreSQL/SQLite (database)
- Pydantic (validation)

**Tools**:
- Nuclei (vulnerability scanner)
- Nmap (port scanner)
- SSLScan (TLS analyzer)

### Multi-Tenancy

- **Tenant Model**: Each user has a tenant (1:1 mapping currently)
- **Isolation**: All queries filter by `Project.tenant_id` and `Project.owner_id`
- **Headers**: `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication
- **Future**: Support for org accounts with multiple users per tenant

### Security Considerations

1. **Authentication**: NextAuth session required for dashboard pages
2. **Authorization**: All API endpoints verify tenant/user ownership
3. **Input Validation**: Pydantic schemas validate all inputs
4. **SQL Injection**: SQLAlchemy ORM prevents SQL injection
5. **Rate Limiting**: Plan-based limits on scans per month
6. **HTTPS Only**: RSS images must be HTTPS

### Performance Optimizations

1. **Parallel RSS Fetching**: All news sources fetched concurrently
2. **Pagination**: Findings and news use pagination
3. **Debouncing**: Search inputs debounced (300ms)
4. **Lazy Loading**: Images loaded lazily
5. **Background Tasks**: Scans run in Celery workers
6. **Database Indexing**: Foreign keys and common filters indexed

---

## File Reference

### News System
- `frontend/app/api/news/route.ts` - RSS aggregation API
- `frontend/app/news/page.tsx` - News page server component
- `frontend/components/News/NewsPageClient.tsx` - Main client component
- `frontend/components/News/NewsClientWrapper.tsx` - Data fetching wrapper

### Vulnerabilities System
- `backend/app/api/findings.py` - Findings API endpoints
- `frontend/components/Dashboard/VulnerabilitiesClient.tsx` - Vulnerabilities UI
- `backend/app/models/finding.py` - Finding database model
- `backend/app/schemas/finding.py` - Pydantic schemas

### Scan System
- `backend/app/api/scans.py` - Scan API endpoints
- `backend/app/services/scan_orchestrator.py` - Scan orchestration
- `backend/app/tasks/celery_app.py` - Celery task definitions
- `backend/app/services/scan_profiles.py` - Scan level configurations
- `backend/app/services/tools.py` - Tool execution

---

## Summary

This documentation covers:
1. **News Page**: RSS aggregation from 7 certified sources, real-time updates, image extraction
2. **Vulnerabilities Page**: Centralized findings view with filtering, search, and status management
3. **Scan Flow**: End-to-end scan execution from API to Celery to database storage

All systems are multi-tenant, secure, and optimized for performance.





## Table of Contents
1. [Security News Page](#security-news-page)
2. [Vulnerabilities Page](#vulnerabilities-page)
3. [Scan Execution Flow](#scan-execution-flow)
4. [Architecture Overview](#architecture-overview)

---

## Security News Page

### Overview
The Security News page (`/news`) aggregates cybersecurity news from trusted RSS feeds, providing real-time threat intelligence to users. It's a public-facing page that doesn't require authentication.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   ├── news/
│   │   ├── page.tsx              # Server component (SEO metadata)
│   │   ├── NewsList.tsx          # News article list renderer
│   │   └── a/[id]/page.tsx       # Individual article detail page
│   └── api/
│       └── news/
│           └── route.ts          # Next.js API route (RSS aggregator)
└── components/
    └── News/
        ├── NewsPageClient.tsx    # Main client wrapper
        ├── NewsClientWrapper.tsx # Data fetching & pagination
        ├── NewsStats.tsx         # Statistics display
        ├── NewsList.tsx          # Article list component
        ├── LoadMoreButton.tsx    # Pagination control
        ├── RightSidebar.tsx      # Sidebar with pinned/latest
        ├── TopSourcesBox.tsx     # Source breakdown
        └── QuickFiltersBox.tsx  # Category filters
```

#### **Data Flow**

```
User Request → /news
    ↓
NewsPageClient (Client Component)
    ↓
NewsClientWrapper
    ↓
GET /api/news?category=cyber&limit=100
    ↓
Next.js API Route (route.ts)
    ↓
RSS Parser (rss-parser library)
    ↓
Fetch from multiple RSS sources (parallel)
    ↓
Normalize & deduplicate
    ↓
Filter by date, category, search
    ↓
Return JSON: { items: [], total: number }
    ↓
Render NewsList component
```

### RSS Sources

All sources are **certified** and fetched via HTTPS. The system aggregates from:

| Source | RSS URL | Category | Certified |
|--------|---------|----------|-----------|
| The Hacker News | `https://feeds.feedburner.com/TheHackersNews` | cyber | ✅ |
| BleepingComputer | `https://www.bleepingcomputer.com/feed/` | cyber | ✅ |
| Krebs on Security | `https://krebsonsecurity.com/feed/` | cyber | ✅ |
| SANS ISC Diary | `https://isc.sans.edu/rssfeed.xml` | cyber | ✅ |
| ZDI (Zero Day Initiative) | `https://www.zerodayinitiative.com/blog?format=rss` | cyber | ✅ |
| Dark Reading | `https://www.darkreading.com/rss.xml` | cyber | ✅ |
| Ars Technica Security | `https://arstechnica.com/security/feed/` | tech | ✅ |

**Location**: `frontend/app/api/news/route.ts:26-37`

### API Endpoint

**Route**: `GET /api/news`

**Query Parameters**:
- `category` (optional): Filter by category (`'cyber' | 'ai' | 'tech'`)
- `sinceDays` (optional, default: `21`): Only return articles from last N days
- `limit` (optional, default: `60`): Maximum number of articles to return
- `certifiedOnly` (optional, default: `'1'`): Only return certified sources (`'1'` or `'0'`)
- `q` (optional): Search query (searches in title, summary, source)

**Response**:
```typescript
{
  items: FeedItem[];
  total: number;
  sources_checked: number;
}

type FeedItem = {
  id: string;              // Format: "Source:URL"
  title: string;
  url: string;
  source: string;
  publishedAt: string;     // ISO 8601
  summary: string;        // Plain text, max 260 chars
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;  // HTTPS image URL or null
  certified: boolean;
}
```

**Location**: `frontend/app/api/news/route.ts:203-262`

### Image Extraction

The system attempts to extract images from RSS feeds using multiple strategies:

1. **RSS Standard Fields**: `enclosure.url`, `media:content`, `media:thumbnail`
2. **HTML Content Parsing**: Extracts `<img>` tags from `content:encoded`
3. **Article Page Fetching** (for specific sources):
   - Only for first 2 articles per source (performance optimization)
   - Sources: BleepingComputer, Krebs on Security, SANS ISC Diary
   - Fetches full HTML and extracts article images
   - Filters out logos, avatars, thumbnails
   - Prefers high-quality article images

**Security**: Only HTTPS images are allowed. Invalid URLs are filtered out.

**Location**: `frontend/app/api/news/route.ts:66-177`

### Data Processing Pipeline

1. **Fetch Phase** (Parallel):
   - All RSS sources are fetched concurrently using `Promise.all()`
   - Each source has a 15-second timeout
   - Failed sources are logged but don't block others

2. **Normalization Phase**:
   - Each RSS item is normalized to `FeedItem` format
   - Extracts: title, URL, published date, summary, image
   - Generates unique ID: `"Source:URL"`

3. **Deduplication Phase**:
   - Uses a `Map<string, FeedItem>` keyed by URL
   - Prevents duplicate articles from different sources

4. **Filtering Phase**:
   - Filters by date (`isRecent()` checks `publishedAt >= sinceMs`)
   - Filters by category (if specified)
   - Filters by certification status (if `certifiedOnly=true`)
   - Filters by search query (title, summary, source)

5. **Sorting Phase**:
   - Sorted by `publishedAt` descending (newest first)

**Location**: `frontend/app/api/news/route.ts:212-250`

### Frontend Components

#### **NewsPageClient** (`components/News/NewsPageClient.tsx`)
- Main client component wrapper
- Manages news state and statistics
- Renders stats bar and main feed layout
- Passes data to `NewsClientWrapper`

#### **NewsClientWrapper** (`components/News/NewsClientWrapper.tsx`)
- Handles data fetching and pagination
- Initial load: fetches first 31 articles
- Load more: fetches next 20 articles
- Manages loading states
- Calls `onStatsUpdate` callback for parent

#### **NewsList** (`app/news/NewsList.tsx`)
- Renders the article list
- Each article shows:
  - Image (if available)
  - Title (link to article)
  - Source badge
  - Published date
  - Summary excerpt
  - Category tag

#### **RightSidebar** (`components/News/RightSidebar.tsx`)
- Displays pinned articles (top 5)
- Shows latest articles
- Source statistics

### Performance Optimizations

1. **Timeout Protection**: 15-second timeout per RSS source
2. **Image Fetching**: Only first 2 articles per source fetch full HTML
3. **Pagination**: Initial load shows 31 articles, load more adds 20
4. **Caching**: Next.js API route uses `force-dynamic` (no caching for real-time data)
5. **Error Handling**: Failed sources don't block the entire feed

---

## Vulnerabilities Page

### Overview
The Vulnerabilities page (`/dashboard/vulnerabilities`) provides a centralized view of all security findings across a user's projects. It supports filtering, searching, and status management.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   └── dashboard/
│       └── vulnerabilities/
│           └── page.tsx           # Server component (auth check)
└── components/
    └── Dashboard/
        └── VulnerabilitiesClient.tsx  # Main client component
```

#### **Backend Structure**

```
backend/
├── app/
│   ├── api/
│   │   └── findings.py            # Findings API endpoints
│   ├── models/
│   │   └── finding.py            # Finding model
│   └── schemas/
│       └── finding.py             # Pydantic schemas
```

### Data Flow

```
User Request → /dashboard/vulnerabilities
    ↓
Server Component (page.tsx)
    ↓
Check NextAuth session
    ↓
VulnerabilitiesClient (Client Component)
    ↓
useSession() → Get session
    ↓
Load Projects (for filter dropdown)
    ↓
GET /api/projects
    ↓
Load Findings (with filters)
    ↓
GET /api/findings?severity=high&status=open&search=...
    ↓
Backend API (findings.py)
    ↓
SQLAlchemy Query (with tenant/user filtering)
    ↓
Return FindingListItem[]
    ↓
Render table with filters
```

### API Endpoints

#### **GET /api/findings**

Lists findings for the current tenant and user.

**Query Parameters**:
- `severity` (optional): Filter by severity (`critical`, `high`, `medium`, `low`, `info`)
- `status` (optional): Filter by status (`open`, `acknowledged`, `resolved`, `suppressed`)
- `tool` (optional): Filter by tool (`nuclei`, `nmap`, `sslscan`)
- `project_id` (optional): Filter by project ID
- `search` (optional): Search in title, description, CVE ID, CWE ID, URL, path
- `limit` (optional, default: `20`): Maximum results per page
- `offset` (optional, default: `0`): Pagination offset

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Response**:
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
  severity: string;           // "critical" | "high" | "medium" | "low" | "info"
  title: string;
  description?: string;
  cve_id?: string;
  cwe_id?: string;
  cvss_score?: number;
  tool: string;               // "nuclei" | "nmap" | "sslscan"
  url?: string;
  path?: string;
  status: string;            // "open" | "acknowledged" | "resolved" | "suppressed"
  first_seen: string;         // ISO 8601
  last_seen: string;         // ISO 8601
}
```

**Location**: `backend/app/api/findings.py:23-138`

#### **PATCH /api/findings/{finding_id}/status**

Updates the workflow status of a finding.

**Request Body**:
```json
{
  "status": "acknowledged"  // "open" | "acknowledged" | "resolved" | "suppressed"
}
```

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Authorization**: Ensures finding belongs to current tenant and user

**Response**: Updated `FindingListItem`

**Location**: `backend/app/api/findings.py:141-213`

### Database Query Structure

The findings query uses SQLAlchemy joins to ensure tenant/user isolation:

```python
query = (
    db.query(Finding, ScanJob, Project)
    .join(ScanJob, Finding.scan_job_id == ScanJob.id)
    .join(Project, ScanJob.project_id == Project.id)
    .filter(
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    )
)
```

**Key Points**:
- Findings are scoped via `Project.tenant_id` and `Project.owner_id`
- Results ordered by `Finding.created_at DESC` (newest first)
- Supports filtering by severity, status, tool, project, and search

**Location**: `backend/app/api/findings.py:49-111`

### Frontend Component

#### **VulnerabilitiesClient** (`components/Dashboard/VulnerabilitiesClient.tsx`)

**State Management**:
- `findings`: Array of findings to display
- `projects`: Array of projects (for filter dropdown)
- `severity`: Selected severity filter
- `selectedStatus`: Selected status filter
- `selectedTool`: Selected tool filter
- `search`: Search query (synced with URL)
- `projectId`: Selected project filter
- `page`: Current page number (pagination)
- `isLoading`: Loading state
- `error`: Error message
- `updatingStatus`: Finding ID being updated (for optimistic UI)

**Features**:
1. **Filtering**:
   - Severity dropdown (Critical, High, Medium, Low, Info)
   - Status dropdown (All, Open, Acknowledged, Resolved, Suppressed)
   - Tool dropdown (All, Nuclei, Nmap, SSLScan)
   - Project dropdown (All projects or specific project)
   - Search input (debounced, 300ms)

2. **URL Sync**:
   - Search query is synced with URL parameter `?search=...`
   - Supports global search integration

3. **Status Updates**:
   - Click status badge to change workflow status
   - Optimistic UI update
   - Calls `PATCH /api/findings/{id}/status`
   - Refetches on success

4. **Navigation**:
   - Project name links to `/projects/{projectId}`
   - "View scan" link to `/projects/{projectId}/scans/{scanId}`

5. **Pagination**:
   - Shows 20 findings per page
   - Previous/Next buttons
   - Displays total count

**Location**: `frontend/components/Dashboard/VulnerabilitiesClient.tsx`

### Security & Multi-Tenancy

- **Tenant Isolation**: All queries filter by `Project.tenant_id`
- **User Isolation**: All queries filter by `Project.owner_id`
- **Authorization**: Status updates verify ownership before allowing changes
- **Headers**: Uses `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication

---

## Scan Execution Flow

### Overview
The scan execution flow handles security scans from API request to completion, using Celery for background task processing.

### Architecture

```
Frontend Request
    ↓
FastAPI Endpoint (/api/scans or /api/scans/quick)
    ↓
Create ScanJob (status: PENDING)
    ↓
ScanOrchestrator.queue_scan()
    ↓
Celery Task (run_scan_task)
    ↓
run_scan_for_job()
    ↓
Scan Profiles (get scan level config)
    ↓
Tool Execution (Nuclei, Nmap, SSLScan)
    ↓
Parse Findings
    ↓
AI Report Generation
    ↓
Update ScanJob (status: COMPLETED)
    ↓
Store Findings in Database
```

### Detailed Flow

#### **Step 1: API Request**

**Endpoints**:
- `POST /api/scans` - Create scan for existing project
- `POST /api/scans/quick` - Quick scan (creates project if needed)

**Request Body** (`POST /api/scans`):
```json
{
  "project_id": "uuid",
  "scan_level": "pro"  // "basic" | "pro" | "advanced"
}
```

**Request Body** (`POST /api/scans/quick`):
```json
{
  "project_id": "uuid",        // Optional
  "target_url": "https://...", // Optional (required if no project_id)
  "scan_level": "pro"
}
```

**Location**: `backend/app/api/scans.py:209-363` and `366-530`

#### **Step 2: Validation & Project Resolution**

1. **Tenant/User Validation**:
   - Validates `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers
   - Ensures project belongs to tenant and user

2. **Plan Limits Check**:
   - Checks monthly scan quota
   - Checks concurrent scan limit
   - Validates scan level is allowed for plan

3. **Project Resolution** (for quick scan):
   - If `project_id` provided: Use existing project
   - If `target_url` provided: Find or create project

**Location**: `backend/app/api/scans.py:234-453`

#### **Step 3: ScanJob Creation**

Creates a `ScanJob` record in the database:

```python
scan_job = ScanJob(
    id=str(uuid.uuid4()),
    project_id=project.id,
    scan_level=ScanLevel(scan_level),
    status=ScanStatus.PENDING,
    tenant_id=tenant.id,
    owner_id=current_user.id,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/api/scans.py:290-315`

#### **Step 4: Celery Task Queueing**

Uses `ScanOrchestrator` to queue the scan:

```python
orchestrator = ScanOrchestrator()
celery_task_id = await orchestrator.queue_scan(
    scan_job.id,
    project.target_url,
    scan_level_str
)
```

**Location**: `backend/app/services/scan_orchestrator.py:19-46`

#### **Step 5: Celery Task Execution**

The Celery worker picks up the task:

```python
@celery.task(name="thandev.run_scan_task")
def run_scan_task(scan_job_id: str, target_url: str, scan_level: str):
    # Update status to RUNNING
    scan_job.status = ScanStatus.RUNNING
    scan_job.started_at = datetime.utcnow()
    
    # Run the scan
    run_scan_for_job(scan_job)
    
    # Update status to COMPLETED/FAILED
    scan_job.status = ScanStatus.COMPLETED
    scan_job.completed_at = datetime.utcnow()
```

**Location**: `backend/app/tasks/celery_app.py:26-96`

#### **Step 6: Scan Execution**

The `run_scan_for_job()` function orchestrates the scan:

1. **Get Scan Profile**:
   - Retrieves tool configuration for scan level
   - Basic: Lightweight tools
   - Pro: Standard tools
   - Advanced: Full tool suite

2. **Run Tools Sequentially**:
   - For each tool in profile:
     - Execute tool via `ToolExecutor.run_tool()`
     - Save output to `data/jobs/{job_id}/{tool}_output.json`
     - Parse findings from output
     - Create `Finding` records in database

3. **AI Report Generation**:
   - Generates executive summary
   - Identifies top risks
   - Calculates risk score
   - Creates remediation overview
   - Stores in `ScanJob.summary` (JSONB)

**Location**: `backend/app/services/scan_orchestrator.py:84-530`

#### **Step 7: Finding Storage**

Findings are stored in the `findings` table:

```python
finding = Finding(
    id=str(uuid.uuid4()),
    scan_job_id=scan_job.id,
    title=parsed_title,
    description=parsed_description,
    severity=Severity(severity),
    status=FindingStatus.OPEN,
    cve_id=cve_id,
    cwe_id=cwe_id,
    cvss_score=cvss_score,
    tool_name=tool_name,
    url=target_url,
    path=file_path,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/services/scan_orchestrator.py:300-450`

### Scan Levels & Tools

| Level | Tools | Description |
|-------|-------|-------------|
| **Basic** | Nuclei (light templates) | Fast surface scan, common vulnerabilities |
| **Pro** | Nuclei (full), Nmap, SSLScan | Deeper coverage, port scanning, TLS analysis |
| **Advanced** | All tools + extended templates | Full-stack probes, comprehensive analysis |

**Location**: `backend/app/services/scan_profiles.py`

### Status Lifecycle

```
PENDING → QUEUED → RUNNING → COMPLETED
                              ↓
                           FAILED (on error)
```

- **PENDING**: ScanJob created, not yet queued
- **QUEUED**: Celery task queued, waiting for worker
- **RUNNING**: Scan in progress
- **COMPLETED**: Scan finished successfully
- **FAILED**: Scan encountered an error

**Location**: `backend/app/models/scan.py:27-34`

### Error Handling

1. **Celery Queue Failure**:
   - Marks scan as `FAILED`
   - Stores error message in `error_message`
   - Returns HTTP 500 with details

2. **Tool Execution Failure**:
   - Logs error
   - Continues with other tools
   - Marks scan as `FAILED` if critical tool fails

3. **Database Errors**:
   - Rolls back transaction
   - Logs error with traceback
   - Returns appropriate HTTP status

**Location**: `backend/app/api/scans.py:331-345` and `backend/app/tasks/celery_app.py:95-120`

### Data Models

#### **ScanJob** (`backend/app/models/scan.py`)
- `id`: UUID
- `project_id`: Foreign key to Project
- `scan_level`: Enum (BASIC, PRO, ADVANCED)
- `status`: Enum (PENDING, QUEUED, RUNNING, COMPLETED, FAILED)
- `summary`: JSONB (AI-generated report)
- `stack_info`: JSONB (stack fingerprinting data)
- `celery_task_id`: Celery task identifier
- `created_at`, `started_at`, `completed_at`: Timestamps

#### **Finding** (`backend/app/models/finding.py`)
- `id`: UUID
- `scan_job_id`: Foreign key to ScanJob
- `title`: Finding title
- `description`: Detailed description
- `severity`: Enum (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- `status`: Enum (OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED)
- `cve_id`, `cwe_id`: Vulnerability identifiers
- `cvss_score`: CVSS score (0.0-10.0)
- `tool_name`: Tool that found it
- `url`, `path`: Location of vulnerability

---

## Architecture Overview

### Technology Stack

**Frontend**:
- Next.js 14 (App Router)
- React 18
- TypeScript
- NextAuth (authentication)
- Tailwind CSS

**Backend**:
- FastAPI
- SQLAlchemy (ORM)
- Celery (task queue)
- PostgreSQL/SQLite (database)
- Pydantic (validation)

**Tools**:
- Nuclei (vulnerability scanner)
- Nmap (port scanner)
- SSLScan (TLS analyzer)

### Multi-Tenancy

- **Tenant Model**: Each user has a tenant (1:1 mapping currently)
- **Isolation**: All queries filter by `Project.tenant_id` and `Project.owner_id`
- **Headers**: `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication
- **Future**: Support for org accounts with multiple users per tenant

### Security Considerations

1. **Authentication**: NextAuth session required for dashboard pages
2. **Authorization**: All API endpoints verify tenant/user ownership
3. **Input Validation**: Pydantic schemas validate all inputs
4. **SQL Injection**: SQLAlchemy ORM prevents SQL injection
5. **Rate Limiting**: Plan-based limits on scans per month
6. **HTTPS Only**: RSS images must be HTTPS

### Performance Optimizations

1. **Parallel RSS Fetching**: All news sources fetched concurrently
2. **Pagination**: Findings and news use pagination
3. **Debouncing**: Search inputs debounced (300ms)
4. **Lazy Loading**: Images loaded lazily
5. **Background Tasks**: Scans run in Celery workers
6. **Database Indexing**: Foreign keys and common filters indexed

---

## File Reference

### News System
- `frontend/app/api/news/route.ts` - RSS aggregation API
- `frontend/app/news/page.tsx` - News page server component
- `frontend/components/News/NewsPageClient.tsx` - Main client component
- `frontend/components/News/NewsClientWrapper.tsx` - Data fetching wrapper

### Vulnerabilities System
- `backend/app/api/findings.py` - Findings API endpoints
- `frontend/components/Dashboard/VulnerabilitiesClient.tsx` - Vulnerabilities UI
- `backend/app/models/finding.py` - Finding database model
- `backend/app/schemas/finding.py` - Pydantic schemas

### Scan System
- `backend/app/api/scans.py` - Scan API endpoints
- `backend/app/services/scan_orchestrator.py` - Scan orchestration
- `backend/app/tasks/celery_app.py` - Celery task definitions
- `backend/app/services/scan_profiles.py` - Scan level configurations
- `backend/app/services/tools.py` - Tool execution

---

## Summary

This documentation covers:
1. **News Page**: RSS aggregation from 7 certified sources, real-time updates, image extraction
2. **Vulnerabilities Page**: Centralized findings view with filtering, search, and status management
3. **Scan Flow**: End-to-end scan execution from API to Celery to database storage

All systems are multi-tenant, secure, and optimized for performance.





## Table of Contents
1. [Security News Page](#security-news-page)
2. [Vulnerabilities Page](#vulnerabilities-page)
3. [Scan Execution Flow](#scan-execution-flow)
4. [Architecture Overview](#architecture-overview)

---

## Security News Page

### Overview
The Security News page (`/news`) aggregates cybersecurity news from trusted RSS feeds, providing real-time threat intelligence to users. It's a public-facing page that doesn't require authentication.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   ├── news/
│   │   ├── page.tsx              # Server component (SEO metadata)
│   │   ├── NewsList.tsx          # News article list renderer
│   │   └── a/[id]/page.tsx       # Individual article detail page
│   └── api/
│       └── news/
│           └── route.ts          # Next.js API route (RSS aggregator)
└── components/
    └── News/
        ├── NewsPageClient.tsx    # Main client wrapper
        ├── NewsClientWrapper.tsx # Data fetching & pagination
        ├── NewsStats.tsx         # Statistics display
        ├── NewsList.tsx          # Article list component
        ├── LoadMoreButton.tsx    # Pagination control
        ├── RightSidebar.tsx      # Sidebar with pinned/latest
        ├── TopSourcesBox.tsx     # Source breakdown
        └── QuickFiltersBox.tsx  # Category filters
```

#### **Data Flow**

```
User Request → /news
    ↓
NewsPageClient (Client Component)
    ↓
NewsClientWrapper
    ↓
GET /api/news?category=cyber&limit=100
    ↓
Next.js API Route (route.ts)
    ↓
RSS Parser (rss-parser library)
    ↓
Fetch from multiple RSS sources (parallel)
    ↓
Normalize & deduplicate
    ↓
Filter by date, category, search
    ↓
Return JSON: { items: [], total: number }
    ↓
Render NewsList component
```

### RSS Sources

All sources are **certified** and fetched via HTTPS. The system aggregates from:

| Source | RSS URL | Category | Certified |
|--------|---------|----------|-----------|
| The Hacker News | `https://feeds.feedburner.com/TheHackersNews` | cyber | ✅ |
| BleepingComputer | `https://www.bleepingcomputer.com/feed/` | cyber | ✅ |
| Krebs on Security | `https://krebsonsecurity.com/feed/` | cyber | ✅ |
| SANS ISC Diary | `https://isc.sans.edu/rssfeed.xml` | cyber | ✅ |
| ZDI (Zero Day Initiative) | `https://www.zerodayinitiative.com/blog?format=rss` | cyber | ✅ |
| Dark Reading | `https://www.darkreading.com/rss.xml` | cyber | ✅ |
| Ars Technica Security | `https://arstechnica.com/security/feed/` | tech | ✅ |

**Location**: `frontend/app/api/news/route.ts:26-37`

### API Endpoint

**Route**: `GET /api/news`

**Query Parameters**:
- `category` (optional): Filter by category (`'cyber' | 'ai' | 'tech'`)
- `sinceDays` (optional, default: `21`): Only return articles from last N days
- `limit` (optional, default: `60`): Maximum number of articles to return
- `certifiedOnly` (optional, default: `'1'`): Only return certified sources (`'1'` or `'0'`)
- `q` (optional): Search query (searches in title, summary, source)

**Response**:
```typescript
{
  items: FeedItem[];
  total: number;
  sources_checked: number;
}

type FeedItem = {
  id: string;              // Format: "Source:URL"
  title: string;
  url: string;
  source: string;
  publishedAt: string;     // ISO 8601
  summary: string;        // Plain text, max 260 chars
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;  // HTTPS image URL or null
  certified: boolean;
}
```

**Location**: `frontend/app/api/news/route.ts:203-262`

### Image Extraction

The system attempts to extract images from RSS feeds using multiple strategies:

1. **RSS Standard Fields**: `enclosure.url`, `media:content`, `media:thumbnail`
2. **HTML Content Parsing**: Extracts `<img>` tags from `content:encoded`
3. **Article Page Fetching** (for specific sources):
   - Only for first 2 articles per source (performance optimization)
   - Sources: BleepingComputer, Krebs on Security, SANS ISC Diary
   - Fetches full HTML and extracts article images
   - Filters out logos, avatars, thumbnails
   - Prefers high-quality article images

**Security**: Only HTTPS images are allowed. Invalid URLs are filtered out.

**Location**: `frontend/app/api/news/route.ts:66-177`

### Data Processing Pipeline

1. **Fetch Phase** (Parallel):
   - All RSS sources are fetched concurrently using `Promise.all()`
   - Each source has a 15-second timeout
   - Failed sources are logged but don't block others

2. **Normalization Phase**:
   - Each RSS item is normalized to `FeedItem` format
   - Extracts: title, URL, published date, summary, image
   - Generates unique ID: `"Source:URL"`

3. **Deduplication Phase**:
   - Uses a `Map<string, FeedItem>` keyed by URL
   - Prevents duplicate articles from different sources

4. **Filtering Phase**:
   - Filters by date (`isRecent()` checks `publishedAt >= sinceMs`)
   - Filters by category (if specified)
   - Filters by certification status (if `certifiedOnly=true`)
   - Filters by search query (title, summary, source)

5. **Sorting Phase**:
   - Sorted by `publishedAt` descending (newest first)

**Location**: `frontend/app/api/news/route.ts:212-250`

### Frontend Components

#### **NewsPageClient** (`components/News/NewsPageClient.tsx`)
- Main client component wrapper
- Manages news state and statistics
- Renders stats bar and main feed layout
- Passes data to `NewsClientWrapper`

#### **NewsClientWrapper** (`components/News/NewsClientWrapper.tsx`)
- Handles data fetching and pagination
- Initial load: fetches first 31 articles
- Load more: fetches next 20 articles
- Manages loading states
- Calls `onStatsUpdate` callback for parent

#### **NewsList** (`app/news/NewsList.tsx`)
- Renders the article list
- Each article shows:
  - Image (if available)
  - Title (link to article)
  - Source badge
  - Published date
  - Summary excerpt
  - Category tag

#### **RightSidebar** (`components/News/RightSidebar.tsx`)
- Displays pinned articles (top 5)
- Shows latest articles
- Source statistics

### Performance Optimizations

1. **Timeout Protection**: 15-second timeout per RSS source
2. **Image Fetching**: Only first 2 articles per source fetch full HTML
3. **Pagination**: Initial load shows 31 articles, load more adds 20
4. **Caching**: Next.js API route uses `force-dynamic` (no caching for real-time data)
5. **Error Handling**: Failed sources don't block the entire feed

---

## Vulnerabilities Page

### Overview
The Vulnerabilities page (`/dashboard/vulnerabilities`) provides a centralized view of all security findings across a user's projects. It supports filtering, searching, and status management.

### Architecture

#### **Frontend Structure**

```
frontend/
├── app/
│   └── dashboard/
│       └── vulnerabilities/
│           └── page.tsx           # Server component (auth check)
└── components/
    └── Dashboard/
        └── VulnerabilitiesClient.tsx  # Main client component
```

#### **Backend Structure**

```
backend/
├── app/
│   ├── api/
│   │   └── findings.py            # Findings API endpoints
│   ├── models/
│   │   └── finding.py            # Finding model
│   └── schemas/
│       └── finding.py             # Pydantic schemas
```

### Data Flow

```
User Request → /dashboard/vulnerabilities
    ↓
Server Component (page.tsx)
    ↓
Check NextAuth session
    ↓
VulnerabilitiesClient (Client Component)
    ↓
useSession() → Get session
    ↓
Load Projects (for filter dropdown)
    ↓
GET /api/projects
    ↓
Load Findings (with filters)
    ↓
GET /api/findings?severity=high&status=open&search=...
    ↓
Backend API (findings.py)
    ↓
SQLAlchemy Query (with tenant/user filtering)
    ↓
Return FindingListItem[]
    ↓
Render table with filters
```

### API Endpoints

#### **GET /api/findings**

Lists findings for the current tenant and user.

**Query Parameters**:
- `severity` (optional): Filter by severity (`critical`, `high`, `medium`, `low`, `info`)
- `status` (optional): Filter by status (`open`, `acknowledged`, `resolved`, `suppressed`)
- `tool` (optional): Filter by tool (`nuclei`, `nmap`, `sslscan`)
- `project_id` (optional): Filter by project ID
- `search` (optional): Search in title, description, CVE ID, CWE ID, URL, path
- `limit` (optional, default: `20`): Maximum results per page
- `offset` (optional, default: `0`): Pagination offset

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Response**:
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
  severity: string;           // "critical" | "high" | "medium" | "low" | "info"
  title: string;
  description?: string;
  cve_id?: string;
  cwe_id?: string;
  cvss_score?: number;
  tool: string;               // "nuclei" | "nmap" | "sslscan"
  url?: string;
  path?: string;
  status: string;            // "open" | "acknowledged" | "resolved" | "suppressed"
  first_seen: string;         // ISO 8601
  last_seen: string;         // ISO 8601
}
```

**Location**: `backend/app/api/findings.py:23-138`

#### **PATCH /api/findings/{finding_id}/status**

Updates the workflow status of a finding.

**Request Body**:
```json
{
  "status": "acknowledged"  // "open" | "acknowledged" | "resolved" | "suppressed"
}
```

**Authentication**: Requires `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers

**Authorization**: Ensures finding belongs to current tenant and user

**Response**: Updated `FindingListItem`

**Location**: `backend/app/api/findings.py:141-213`

### Database Query Structure

The findings query uses SQLAlchemy joins to ensure tenant/user isolation:

```python
query = (
    db.query(Finding, ScanJob, Project)
    .join(ScanJob, Finding.scan_job_id == ScanJob.id)
    .join(Project, ScanJob.project_id == Project.id)
    .filter(
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    )
)
```

**Key Points**:
- Findings are scoped via `Project.tenant_id` and `Project.owner_id`
- Results ordered by `Finding.created_at DESC` (newest first)
- Supports filtering by severity, status, tool, project, and search

**Location**: `backend/app/api/findings.py:49-111`

### Frontend Component

#### **VulnerabilitiesClient** (`components/Dashboard/VulnerabilitiesClient.tsx`)

**State Management**:
- `findings`: Array of findings to display
- `projects`: Array of projects (for filter dropdown)
- `severity`: Selected severity filter
- `selectedStatus`: Selected status filter
- `selectedTool`: Selected tool filter
- `search`: Search query (synced with URL)
- `projectId`: Selected project filter
- `page`: Current page number (pagination)
- `isLoading`: Loading state
- `error`: Error message
- `updatingStatus`: Finding ID being updated (for optimistic UI)

**Features**:
1. **Filtering**:
   - Severity dropdown (Critical, High, Medium, Low, Info)
   - Status dropdown (All, Open, Acknowledged, Resolved, Suppressed)
   - Tool dropdown (All, Nuclei, Nmap, SSLScan)
   - Project dropdown (All projects or specific project)
   - Search input (debounced, 300ms)

2. **URL Sync**:
   - Search query is synced with URL parameter `?search=...`
   - Supports global search integration

3. **Status Updates**:
   - Click status badge to change workflow status
   - Optimistic UI update
   - Calls `PATCH /api/findings/{id}/status`
   - Refetches on success

4. **Navigation**:
   - Project name links to `/projects/{projectId}`
   - "View scan" link to `/projects/{projectId}/scans/{scanId}`

5. **Pagination**:
   - Shows 20 findings per page
   - Previous/Next buttons
   - Displays total count

**Location**: `frontend/components/Dashboard/VulnerabilitiesClient.tsx`

### Security & Multi-Tenancy

- **Tenant Isolation**: All queries filter by `Project.tenant_id`
- **User Isolation**: All queries filter by `Project.owner_id`
- **Authorization**: Status updates verify ownership before allowing changes
- **Headers**: Uses `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication

---

## Scan Execution Flow

### Overview
The scan execution flow handles security scans from API request to completion, using Celery for background task processing.

### Architecture

```
Frontend Request
    ↓
FastAPI Endpoint (/api/scans or /api/scans/quick)
    ↓
Create ScanJob (status: PENDING)
    ↓
ScanOrchestrator.queue_scan()
    ↓
Celery Task (run_scan_task)
    ↓
run_scan_for_job()
    ↓
Scan Profiles (get scan level config)
    ↓
Tool Execution (Nuclei, Nmap, SSLScan)
    ↓
Parse Findings
    ↓
AI Report Generation
    ↓
Update ScanJob (status: COMPLETED)
    ↓
Store Findings in Database
```

### Detailed Flow

#### **Step 1: API Request**

**Endpoints**:
- `POST /api/scans` - Create scan for existing project
- `POST /api/scans/quick` - Quick scan (creates project if needed)

**Request Body** (`POST /api/scans`):
```json
{
  "project_id": "uuid",
  "scan_level": "pro"  // "basic" | "pro" | "advanced"
}
```

**Request Body** (`POST /api/scans/quick`):
```json
{
  "project_id": "uuid",        // Optional
  "target_url": "https://...", // Optional (required if no project_id)
  "scan_level": "pro"
}
```

**Location**: `backend/app/api/scans.py:209-363` and `366-530`

#### **Step 2: Validation & Project Resolution**

1. **Tenant/User Validation**:
   - Validates `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` headers
   - Ensures project belongs to tenant and user

2. **Plan Limits Check**:
   - Checks monthly scan quota
   - Checks concurrent scan limit
   - Validates scan level is allowed for plan

3. **Project Resolution** (for quick scan):
   - If `project_id` provided: Use existing project
   - If `target_url` provided: Find or create project

**Location**: `backend/app/api/scans.py:234-453`

#### **Step 3: ScanJob Creation**

Creates a `ScanJob` record in the database:

```python
scan_job = ScanJob(
    id=str(uuid.uuid4()),
    project_id=project.id,
    scan_level=ScanLevel(scan_level),
    status=ScanStatus.PENDING,
    tenant_id=tenant.id,
    owner_id=current_user.id,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/api/scans.py:290-315`

#### **Step 4: Celery Task Queueing**

Uses `ScanOrchestrator` to queue the scan:

```python
orchestrator = ScanOrchestrator()
celery_task_id = await orchestrator.queue_scan(
    scan_job.id,
    project.target_url,
    scan_level_str
)
```

**Location**: `backend/app/services/scan_orchestrator.py:19-46`

#### **Step 5: Celery Task Execution**

The Celery worker picks up the task:

```python
@celery.task(name="thandev.run_scan_task")
def run_scan_task(scan_job_id: str, target_url: str, scan_level: str):
    # Update status to RUNNING
    scan_job.status = ScanStatus.RUNNING
    scan_job.started_at = datetime.utcnow()
    
    # Run the scan
    run_scan_for_job(scan_job)
    
    # Update status to COMPLETED/FAILED
    scan_job.status = ScanStatus.COMPLETED
    scan_job.completed_at = datetime.utcnow()
```

**Location**: `backend/app/tasks/celery_app.py:26-96`

#### **Step 6: Scan Execution**

The `run_scan_for_job()` function orchestrates the scan:

1. **Get Scan Profile**:
   - Retrieves tool configuration for scan level
   - Basic: Lightweight tools
   - Pro: Standard tools
   - Advanced: Full tool suite

2. **Run Tools Sequentially**:
   - For each tool in profile:
     - Execute tool via `ToolExecutor.run_tool()`
     - Save output to `data/jobs/{job_id}/{tool}_output.json`
     - Parse findings from output
     - Create `Finding` records in database

3. **AI Report Generation**:
   - Generates executive summary
   - Identifies top risks
   - Calculates risk score
   - Creates remediation overview
   - Stores in `ScanJob.summary` (JSONB)

**Location**: `backend/app/services/scan_orchestrator.py:84-530`

#### **Step 7: Finding Storage**

Findings are stored in the `findings` table:

```python
finding = Finding(
    id=str(uuid.uuid4()),
    scan_job_id=scan_job.id,
    title=parsed_title,
    description=parsed_description,
    severity=Severity(severity),
    status=FindingStatus.OPEN,
    cve_id=cve_id,
    cwe_id=cwe_id,
    cvss_score=cvss_score,
    tool_name=tool_name,
    url=target_url,
    path=file_path,
    created_at=datetime.now(timezone.utc)
)
```

**Location**: `backend/app/services/scan_orchestrator.py:300-450`

### Scan Levels & Tools

| Level | Tools | Description |
|-------|-------|-------------|
| **Basic** | Nuclei (light templates) | Fast surface scan, common vulnerabilities |
| **Pro** | Nuclei (full), Nmap, SSLScan | Deeper coverage, port scanning, TLS analysis |
| **Advanced** | All tools + extended templates | Full-stack probes, comprehensive analysis |

**Location**: `backend/app/services/scan_profiles.py`

### Status Lifecycle

```
PENDING → QUEUED → RUNNING → COMPLETED
                              ↓
                           FAILED (on error)
```

- **PENDING**: ScanJob created, not yet queued
- **QUEUED**: Celery task queued, waiting for worker
- **RUNNING**: Scan in progress
- **COMPLETED**: Scan finished successfully
- **FAILED**: Scan encountered an error

**Location**: `backend/app/models/scan.py:27-34`

### Error Handling

1. **Celery Queue Failure**:
   - Marks scan as `FAILED`
   - Stores error message in `error_message`
   - Returns HTTP 500 with details

2. **Tool Execution Failure**:
   - Logs error
   - Continues with other tools
   - Marks scan as `FAILED` if critical tool fails

3. **Database Errors**:
   - Rolls back transaction
   - Logs error with traceback
   - Returns appropriate HTTP status

**Location**: `backend/app/api/scans.py:331-345` and `backend/app/tasks/celery_app.py:95-120`

### Data Models

#### **ScanJob** (`backend/app/models/scan.py`)
- `id`: UUID
- `project_id`: Foreign key to Project
- `scan_level`: Enum (BASIC, PRO, ADVANCED)
- `status`: Enum (PENDING, QUEUED, RUNNING, COMPLETED, FAILED)
- `summary`: JSONB (AI-generated report)
- `stack_info`: JSONB (stack fingerprinting data)
- `celery_task_id`: Celery task identifier
- `created_at`, `started_at`, `completed_at`: Timestamps

#### **Finding** (`backend/app/models/finding.py`)
- `id`: UUID
- `scan_job_id`: Foreign key to ScanJob
- `title`: Finding title
- `description`: Detailed description
- `severity`: Enum (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- `status`: Enum (OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED)
- `cve_id`, `cwe_id`: Vulnerability identifiers
- `cvss_score`: CVSS score (0.0-10.0)
- `tool_name`: Tool that found it
- `url`, `path`: Location of vulnerability

---

## Architecture Overview

### Technology Stack

**Frontend**:
- Next.js 14 (App Router)
- React 18
- TypeScript
- NextAuth (authentication)
- Tailwind CSS

**Backend**:
- FastAPI
- SQLAlchemy (ORM)
- Celery (task queue)
- PostgreSQL/SQLite (database)
- Pydantic (validation)

**Tools**:
- Nuclei (vulnerability scanner)
- Nmap (port scanner)
- SSLScan (TLS analyzer)

### Multi-Tenancy

- **Tenant Model**: Each user has a tenant (1:1 mapping currently)
- **Isolation**: All queries filter by `Project.tenant_id` and `Project.owner_id`
- **Headers**: `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` for authentication
- **Future**: Support for org accounts with multiple users per tenant

### Security Considerations

1. **Authentication**: NextAuth session required for dashboard pages
2. **Authorization**: All API endpoints verify tenant/user ownership
3. **Input Validation**: Pydantic schemas validate all inputs
4. **SQL Injection**: SQLAlchemy ORM prevents SQL injection
5. **Rate Limiting**: Plan-based limits on scans per month
6. **HTTPS Only**: RSS images must be HTTPS

### Performance Optimizations

1. **Parallel RSS Fetching**: All news sources fetched concurrently
2. **Pagination**: Findings and news use pagination
3. **Debouncing**: Search inputs debounced (300ms)
4. **Lazy Loading**: Images loaded lazily
5. **Background Tasks**: Scans run in Celery workers
6. **Database Indexing**: Foreign keys and common filters indexed

---

## File Reference

### News System
- `frontend/app/api/news/route.ts` - RSS aggregation API
- `frontend/app/news/page.tsx` - News page server component
- `frontend/components/News/NewsPageClient.tsx` - Main client component
- `frontend/components/News/NewsClientWrapper.tsx` - Data fetching wrapper

### Vulnerabilities System
- `backend/app/api/findings.py` - Findings API endpoints
- `frontend/components/Dashboard/VulnerabilitiesClient.tsx` - Vulnerabilities UI
- `backend/app/models/finding.py` - Finding database model
- `backend/app/schemas/finding.py` - Pydantic schemas

### Scan System
- `backend/app/api/scans.py` - Scan API endpoints
- `backend/app/services/scan_orchestrator.py` - Scan orchestration
- `backend/app/tasks/celery_app.py` - Celery task definitions
- `backend/app/services/scan_profiles.py` - Scan level configurations
- `backend/app/services/tools.py` - Tool execution

---

## Summary

This documentation covers:
1. **News Page**: RSS aggregation from 7 certified sources, real-time updates, image extraction
2. **Vulnerabilities Page**: Centralized findings view with filtering, search, and status management
3. **Scan Flow**: End-to-end scan execution from API to Celery to database storage

All systems are multi-tenant, secure, and optimized for performance.





