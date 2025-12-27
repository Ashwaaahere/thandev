# Thandev Brain Service

## Scope

The Thandev Brain service is a separate FastAPI service located in `services/thandev-brain/`. It provides RAG (Retrieval-Augmented Generation) powered intelligence for scan planning and report prompt generation.

**Key Principle**: The Brain service does NOT execute tools or generate reports directly. It provides planning and prompt building services that the backend uses.

## Directory Structure

```
services/thandev-brain/
├── app/
│   ├── main.py              # FastAPI app entrypoint
│   ├── api/
│   │   ├── v1.py           # API v1 endpoints
│   │   └── rag.py          # RAG management endpoints
│   ├── models.py           # Pydantic request/response models
│   ├── catalog.py          # Tool catalog loader
│   ├── core/
│   │   └── config.py       # Settings
│   ├── planner/
│   │   └── plan.py         # Scan plan generation (rules + RAG)
│   ├── report_prompt/
│   │   └── builder.py      # Report prompt package builder
│   └── rag/
│       ├── store.py        # RAG storage interface (Qdrant/PgVector)
│       └── embeddings.py   # Embedding provider abstraction
├── catalog/
│   └── catalog.json        # Tool catalog definition
└── requirements.txt
```

## Responsibilities

### 1. Scan Planning

**Function**: Generate intelligent scan plans based on target characteristics.

**Input**: Target URL, scan level, optional stack info (HTTP headers, server info)

**Output**: `PlanScanResponse` with:
- List of tool steps (`tool_id`, `mode_id`, `params`, `depends_on`)
- Timeline estimates
- Reasoning/explanation

**Process**:
1. Load tool catalog
2. Apply rules-based filtering (scan level, tool availability)
3. Use RAG to retrieve relevant knowledge (past scans, CVE data, best practices)
4. Generate plan using LLM (if configured) or rule-based logic
5. Return structured plan

### 2. Report Prompt Building

**Function**: Build comprehensive prompt packages for OpenAI report generation.

**Input**: Finding IDs, scan metadata

**Output**: `BuildReportPromptResponse` with:
- System prompt
- User prompt with findings context
- Supporting evidence from RAG
- Instructions for report structure

**Process**:
1. Load normalized findings from database (via finding IDs)
2. Retrieve supporting evidence from RAG (CVE details, remediation guidance)
3. Build structured prompt package
4. Return prompt package (backend sends to OpenAI)

### 3. Finding Enrichment (Optional)

**Function**: Enrich findings with impact summaries and remediation guidance.

**Status**: Endpoint exists (`/v1/enrich-findings`) but may not be fully integrated into scan pipeline.

## Data Sources

### Vector Store (RAG Knowledge Base)

**Supported Backends:**
- **Qdrant**: Default vector database (recommended)
- **PgVector**: PostgreSQL vector extension (alternative)

**What Goes Into RAG:**
- CVE descriptions and references (from NVD)
- Security tool documentation
- Past scan results (if indexed)
- Security best practices and remediation guides
- Vulnerability patterns and signatures

**Collection Name**: `thandev_rag` (configurable)

### Tool Catalog

**Location**: `catalog/catalog.json`

**Structure**:
- Tools: List of available security tools (nuclei, nmap, httpx, etc.)
- Modes: Execution modes per tool (e.g., `nuclei-fast`, `nuclei-deep`)
- Metadata: Tool descriptions, capabilities, requirements

**Usage**: Brain service loads catalog to understand available tools and modes for planning.

## API Endpoints

### Health Check

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "ok",
  "service": "thandev-brain"
}
```

### Get Catalog

**Endpoint**: `GET /v1/catalog`

**Response**: `CatalogResponse`
```json
{
  "tools": [...],
  "modes": [...],
  "metadata": {...}
}
```

**Caller**: Backend (for validation), Frontend (for UI display)

### Plan Scan

**Endpoint**: `POST /v1/plan-scan`

**Request**: `PlanScanRequest`
```json
{
  "target_url": "https://example.com",
  "scan_level": "pro",
  "org_id": "optional-org-id",
  "project_id": "optional-project-id",
  "stack_info": {
    "target_url": "https://example.com",
    "scan_level": "pro",
    "http": {
      "status_code": 200,
      "headers": {
        "server": "nginx",
        "content_type": "text/html"
      }
    }
  }
}
```

**Response**: `PlanScanResponse`
```json
{
  "steps": [
    {
      "step_id": "step-1",
      "tool_id": "nuclei",
      "mode_id": "nuclei-fast",
      "params": {},
      "depends_on": [],
      "estimated_duration_sec": 300
    }
  ],
  "timeline": {
    "estimated_total_sec": 600,
    "parallel_steps": 2
  },
  "reasoning": "Selected nuclei-fast for quick vulnerability scanning..."
}
```

**Caller**: Backend (`scan_orchestrator.py`) during scan creation

**Timeout**: 30 seconds (configurable via `BRAIN_SERVICE_TIMEOUT`)

### Build Report Prompt

**Endpoint**: `POST /v1/build-report-prompt`

**Request**: `BuildReportPromptRequest`
```json
{
  "finding_ids": ["finding-id-1", "finding-id-2"],
  "scan_metadata": {
    "target_url": "https://example.com",
    "scan_level": "pro",
    "scan_id": "scan-job-id"
  }
}
```

**Response**: `BuildReportPromptResponse`
```json
{
  "system_prompt": "You are a security expert...",
  "user_prompt": "Generate a report for the following findings...",
  "supporting_evidence": [
    {
      "source": "CVE-2023-1234",
      "content": "Cross-site scripting vulnerability..."
    }
  ],
  "instructions": {
    "format": "json",
    "sections": ["executive_summary", "findings", "recommendations"]
  }
}
```

**Caller**: Backend during report generation (if AI enrichment enabled)

### Enrich Findings

**Endpoint**: `POST /v1/enrich-findings`

**Request**: `EnrichFindingsRequest`
```json
{
  "finding_ids": ["finding-id-1", "finding-id-2"],
  "org_id": "optional-org-id"
}
```

**Response**: `EnrichFindingsResponse`
```json
{
  "enriched_findings": [
    {
      "finding_id": "finding-id-1",
      "impact_summary": "An attacker can...",
      "remediation_summary": "Sanitize input...",
      "remediation_steps": ["Step 1", "Step 2"]
    }
  ]
}
```

**Status**: Endpoint exists but may not be fully integrated into scan pipeline.

**Caller**: Backend (if finding enrichment is enabled)

## LLM Usage

### Configuration

**Environment Variables:**
- `OPENAI_API_KEY`: OpenAI API key (required for LLM features)
- `OPENAI_MODEL`: Model to use (default: `gpt-4` or `gpt-3.5-turbo`)
- `OPENAI_EMBEDDING_MODEL`: Embedding model (default: `text-embedding-3-small`)

**Embedding Provider:**
- `EMBEDDING_PROVIDER`: `openai` or `sentence_transformers`
- If `sentence_transformers`: Uses local model (no API key needed)
- If `openai`: Uses OpenAI embeddings API

### Temperature and Tokens

**Temperature**: Configurable per endpoint (default: 0.7 for planning, 0.3 for report prompts)

**Max Tokens**: Configurable (default: 2000 for planning, 4000 for report prompts)

**Cost Controls**: 
- No explicit cost controls in codebase
- Relies on OpenAI API rate limits
- Consider implementing token budgets for production

## Safety / Guardrail Measures

**Input Validation:**
- Pydantic models validate all request inputs
- URL validation for target URLs
- Scan level validation (must be "basic", "pro", or "advanced")

**Error Handling:**
- All endpoints wrapped in try/except
- Returns HTTP 400 for invalid requests
- Returns HTTP 500 for internal errors
- Logs errors with full stack traces

**Timeout Protection:**
- HTTP client timeouts (30 seconds default)
- Prevents hanging requests

**RAG Safety:**
- Vector search results limited (top K results)
- No user-controlled data directly injected into prompts (findings are normalized)

## Integration with Backend

**Backend Client**: `backend/app/services/brain_client.py`

**Usage Pattern:**
```python
from app.services.brain_client import get_brain_client

brain_client = get_brain_client()
plan = await brain_client.create_plan(
    target_url=target_url,
    scan_level=scan_level,
    stack_info=stack_info
)
```

**Fallback Behavior:**
- If `BRAIN_SERVICE_ENABLED=false`: Backend uses rule-based tool selection
- If brain service unreachable and `BRAIN_REQUIRED=false`: Backend falls back to Celery-based planning
- If `BRAIN_REQUIRED=true`: Scan fails if brain unavailable

## Configuration

**Environment Variables:**

**Service:**
- `ENVIRONMENT`: `development` or `production`
- `DEBUG`: Enable debug logging
- `CORS_ORIGINS`: Comma-separated allowed origins

**RAG Storage:**
- `RAG_STORE_TYPE`: `qdrant` or `pgvector`
- `QDRANT_URL`: Qdrant server URL (default: `http://localhost:6333`)
- `QDRANT_COLLECTION`: Collection name (default: `thandev_rag`)
- `DATABASE_URL`: PostgreSQL connection (for PgVector)

**Embeddings:**
- `EMBEDDING_PROVIDER`: `openai` or `sentence_transformers`
- `EMBEDDING_MODEL`: Model name (e.g., `all-MiniLM-L6-v2` for sentence-transformers)
- `OPENAI_API_KEY`: OpenAI API key
- `OPENAI_EMBEDDING_MODEL`: OpenAI embedding model (default: `text-embedding-3-small`)

**Brain Limits:**
- `BRAIN_MAX_STEPS`: Maximum steps in a plan (default: 20)
- `BRAIN_MAX_PARALLELISM`: Maximum parallel steps (default: 5)
- `BRAIN_MAX_TOTAL_RUNTIME_SEC`: Maximum total scan runtime (default: 3600)

## Running the Service

**Development:**
```bash
cd services/thandev-brain
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**Production:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**Health Check:**
```bash
curl http://localhost:8001/health
```

## Dependencies

**Core:**
- `fastapi`: Web framework
- `httpx`: HTTP client (for OpenAI API)
- `pydantic`: Data validation

**RAG:**
- `qdrant-client`: Qdrant vector database client (if using Qdrant)
- `pgvector`: PostgreSQL vector extension (if using PgVector)
- `sentence-transformers`: Local embeddings (if not using OpenAI)

**LLM:**
- `openai`: OpenAI API client (if using OpenAI)

**See**: `requirements.txt` for full dependency list

