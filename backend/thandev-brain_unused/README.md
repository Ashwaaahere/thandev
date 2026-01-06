# Thandev Brain Service

RAG-powered scan planning and report prompt generation service for Thandev.

## Overview

The Brain Service is a separate FastAPI service that:
- Generates scan plans (tool_id, mode_id, params, dependencies, timeline)
- Builds report prompt packages for OpenAI
- Uses RAG (Retrieval-Augmented Generation) to inform decisions
- Does NOT execute tools or generate reports directly

## Architecture

```
services/thandev-brain/
├── app/
│   ├── main.py              # FastAPI app entrypoint
│   ├── api/v1.py           # API endpoints
│   ├── models.py         # Pydantic request/response models
│   ├── catalog.py        # Tool catalog loader
│   ├── core/
│   │   └── config.py     # Settings
│   ├── planner/
│   │   └── plan.py       # Scan plan generation (rules + RAG)
│   ├── report_prompt/
│   │   └── builder.py    # Report prompt package builder
│   └── rag/
│       ├── store.py      # RAG storage interface (Qdrant/PgVector)
│       └── embeddings.py # Embedding providers
├── catalog/
│   └── catalog.json      # Tool catalog definition
└── requirements.txt
```

## Installation

```bash
cd services/thandev-brain
pip install -r requirements.txt

# Optional: Install RAG dependencies based on configuration
# For Qdrant:
# pip install qdrant-client

# For PgVector:
# pip install sqlalchemy pgvector

# For embeddings:
# pip install sentence-transformers  # or openai
```

## Configuration

Create a `.env` file:

```env
# Service
ENVIRONMENT=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# RAG Storage
RAG_STORE_TYPE=qdrant  # or pgvector
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=thandev_rag

# PostgreSQL (for pgvector)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev

# Embeddings
EMBEDDING_PROVIDER=sentence_transformers  # or openai
EMBEDDING_MODEL=all-MiniLM-L6-v2
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Brain Limits
BRAIN_MAX_STEPS=20
BRAIN_MAX_PARALLELISM=5
BRAIN_MAX_TOTAL_RUNTIME_SEC=3600
```

## Running

```bash
# Development
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## API Endpoints

See [BRAIN_API.md](../../docs/BRAIN_API.md) for full API documentation.

### Quick Examples

**Get catalog:**
```bash
curl http://localhost:8001/v1/catalog
```

**Plan a scan:**
```bash
curl -X POST http://localhost:8001/v1/plan-scan \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "scan_level": "pro",
    "stack_info": {
      "http": {
        "status_code": 200,
        "headers": {"server": "nginx"}
      }
    }
  }'
```

**Build report prompt:**
```bash
curl -X POST http://localhost:8001/v1/build-report-prompt \
  -H "Content-Type: application/json" \
  -d '{
    "scan_job_id": "scan-123",
    "finding_ids": ["finding-1", "finding-2"]
  }'
```

## Development Status

- ✅ Phase 1: Service skeleton + contracts
- ⏳ Phase 2: RAG foundation (stub implementations)
- ⏳ Phase 3: /plan-scan with rules + RAG
- ⏳ Phase 4: /build-report-prompt with evidence packing
- ⏳ Phase 5: Core backend integration

## Notes

- The brain service is designed to be stateless (except for RAG storage)
- All validation uses Pydantic with `additionalProperties: false`
- Tool execution remains in the core backend
- Report generation (OpenAI calls) remains in the core backend




