# Thandev Brain Service - Implementation Status

## Summary

This document tracks the implementation status of the Thandev Brain Service, a RAG-powered service for scan planning and report prompt generation.

## Completed Phases

### Phase 0: Repository Audit & Documentation ✅

**Deliverables:**
- `docs/REPO_MAP.md`: Complete repository structure, services, data model, scan flow
- `docs/CURRENT_SCAN_FLOW.md`: Detailed sequence diagram, tool execution flow, findings normalization, artifact definitions

**Key Findings:**
- Core backend: FastAPI with PostgreSQL/SQLite, Celery for task queue
- Scan execution: Orchestrator → ToolExecutor → Findings Ingestor
- Current AI: Basic planner and reporter (rule-based, some OpenAI integration)
- Artifacts: Tool output files + DB records (ToolResult, Finding)

### Phase 1: Brain Service Skeleton ✅

**Deliverables:**
- `services/thandev-brain/`: Complete FastAPI service structure
- `packages/thandev_schemas/`: Shared Pydantic schemas
- `catalog/catalog.json`: Tool catalog with tools, modes, params_schema
- `docs/BRAIN_API.md`: API documentation

**Implemented:**
- FastAPI app with `/health`, `/catalog`, `/plan-scan`, `/build-report-prompt` endpoints
- Pydantic models with `additionalProperties: false` validation
- Tool catalog loader
- Stub implementations for planner and report_prompt builder
- RAG store interface (Qdrant/PgVector) - stub implementations
- Embedding provider interface (SentenceTransformers/OpenAI) - stub implementations

**Files Created:**
```
services/thandev-brain/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── catalog.py
│   ├── api/v1.py
│   ├── core/config.py
│   ├── planner/plan.py (stub)
│   ├── report_prompt/builder.py (stub)
│   └── rag/
│       ├── store.py (stub)
│       └── embeddings.py (stub)
├── catalog/catalog.json
└── requirements.txt

packages/thandev_schemas/
├── __init__.py
├── catalog.py
├── planning.py
└── reporting.py
```

## In Progress

### Phase 2: RAG Foundation ⏳

**Status:** Stub implementations created, need full implementation

**TODO:**
- [ ] Implement QdrantRagStore.upsert_documents() and query()
- [ ] Implement PgVectorRagStore.upsert_documents() and query()
- [ ] Create document ingestion utilities for:
  - Prior scan findings (normalized)
  - Tool artifact summaries
  - Tech fingerprint
  - Template/CVE metadata
- [ ] Add metadata fields (org_id, project_id, target, doc_type, tool_id, severity, created_at)
- [ ] Create `docs/RAG_DESIGN.md` with retrieval lanes

## Pending Phases

### Phase 3: /plan-scan Implementation

**Requirements:**
- RAG retrieval from multiple lanes:
  - Latest findings for project/target
  - Tech fingerprint
  - Template/CVE hints
- Deterministic rules:
  - TLS endpoint → add sslyze mode
  - Prior CVE signals → nuclei cve_fast confirm mode
  - Params-based app fingerprint → dalfox constrained mode
- Plan validation:
  - Tool/mode exists in catalog
  - Params validate against params_schema
  - DAG is acyclic
  - Policy limits enforced (max_steps, max_parallelism, max_total_runtime_sec)
- Tests: `tests/test_plan_validation.py`

### Phase 4: /build-report-prompt Implementation

**Requirements:**
- Load normalized findings from core-provided IDs
- Retrieve supporting evidence from RAG
- Return prompt package:
  - System message: "Do not invent; all findings must cite evidence"
  - User content: project + targets + findings + evidence objects
  - report_json_schema (strict) for OpenAI Structured Outputs
  - artifact_index with evidence_refs
- Documentation: `docs/REPORT_PROMPT_CONTRACT.md`

### Phase 5: Core Backend Integration

**Requirements:**
- Add `core/services/brain_client.py`:
  - `create_plan(...)` calls `/v1/plan-scan`
  - `build_report_prompt(...)` calls `/v1/build-report-prompt`
- Server-side validation gates:
  - Verify tool_id/mode_id exists in local catalog copy
  - Enforce scope rules
  - Enforce quotas
- Documentation: `docs/BRAIN_INTEGRATION.md`

## Architecture Decisions

1. **Separation of Concerns:**
   - Brain: Planning and prompt generation only
   - Core: Tool execution, findings storage, OpenAI report generation

2. **Schema Validation:**
   - All Pydantic models use `additionalProperties: false`
   - JSON Schema validation for tool params

3. **RAG Storage:**
   - Pluggable: Qdrant (default) or PgVector
   - Embeddings: SentenceTransformers (default) or OpenAI

4. **Catalog Design:**
   - No command strings in catalog
   - Runner owns command mapping
   - Catalog defines tool_id, mode_id, params_schema, constraints

## How to Run Brain Service Locally

### Prerequisites

```bash
# Install dependencies
cd services/thandev-brain
pip install -r requirements.txt

# Optional: Install RAG dependencies
pip install qdrant-client  # For Qdrant
# OR
pip install sqlalchemy pgvector  # For PgVector

# Optional: Install embedding provider
pip install sentence-transformers  # Default
# OR
pip install openai  # For OpenAI embeddings
```

### Configuration

Create `services/thandev-brain/.env`:

```env
ENVIRONMENT=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=thandev_rag

EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Run with Docker Compose (Recommended)

Add to `docker-compose.yml`:

```yaml
  brain:
    build: ./services/thandev-brain
    ports:
      - "8001:8001"
    environment:
      RAG_STORE_TYPE: qdrant
      QDRANT_URL: http://qdrant:6333
    depends_on:
      - qdrant

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

### Run Standalone

```bash
cd services/thandev-brain
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8001/health

# Get catalog
curl http://localhost:8001/v1/catalog

# Plan scan
curl -X POST http://localhost:8001/v1/plan-scan \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "scan_level": "pro"
  }'
```

## Example Requests

### Plan Scan Request

```bash
curl -X POST http://localhost:8001/v1/plan-scan \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "scan_level": "pro",
    "org_id": "org-123",
    "project_id": "project-456",
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
  }'
```

### Build Report Prompt Request

```bash
curl -X POST http://localhost:8001/v1/build-report-prompt \
  -H "Content-Type: application/json" \
  -d '{
    "scan_job_id": "scan-123",
    "finding_ids": ["finding-1", "finding-2"],
    "artifact_refs": [
      {
        "tool_name": "nuclei",
        "file_path": "data/jobs/scan-123/nuclei_output.json"
      }
    ],
    "org_id": "org-123",
    "project_id": "project-456"
  }'
```

## Next Steps

1. **Complete Phase 2:** Implement full RAG store and embedding providers
2. **Complete Phase 3:** Add RAG retrieval and rules to `/plan-scan`
3. **Complete Phase 4:** Implement evidence packing in `/build-report-prompt`
4. **Complete Phase 5:** Integrate with core backend
5. **Testing:** Add unit tests and integration tests
6. **Documentation:** Complete RAG design doc and integration guide

## Checklist

- [x] Phase 0: Repository audit and documentation
- [x] Phase 1: Brain service skeleton + contracts
- [ ] Phase 2: RAG foundation (in progress)
- [ ] Phase 3: /plan-scan with rules + RAG
- [ ] Phase 4: /build-report-prompt with evidence
- [ ] Phase 5: Core backend integration




