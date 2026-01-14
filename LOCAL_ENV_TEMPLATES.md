# Local Environment Templates

Copy the snippets below into your local `.env` files (do **not** commit secrets). Adjust values as needed.

## backend/.env
```
ENVIRONMENT=development
DEBUG=false

# Core URLs
BACKEND_URL=http://localhost:8000

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=

# Auth / security
SECRET_KEY=change-me-for-local
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Runner auth (set same in runner .env)
RUNNER_API_TOKEN=change-me-runner-token

# Brain / planner
BRAIN_SERVICE_ENABLED=true
BRAIN_REQUIRED=false
BRAIN_SERVICE_URL=http://localhost:8001
BRAIN_URL=http://localhost:8001
BRAIN_SERVICE_TIMEOUT=60

# Tenant / setup
SELF_SERVICE_SIGNUP_ENABLED=1
THANDEV_SETUP_TOKEN=
THANDEV_SUPERADMIN_EXTERNAL_IDS=

# Optional
CALLBACK_SECRET=local-callback-secret
INTERNAL_ENDPOINT_REQUIRE_PRIVATE_NETWORK=
```

## services/thandev-runner/.env
```
ENVIRONMENT=development
DEBUG=false

# Backend API the runner posts to
BACKEND_URL=http://localhost:8000
RUNNER_API_TOKEN=change-me-runner-token

# Shared DB/Redis (must match backend)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
REDIS_URL=redis://localhost:6379/0

# Concurrency / execution
EXECUTION_ADAPTER=local
MAX_CONCURRENT_STEPS=20
MAX_INFLIGHT_PER_SESSION=100

# Wordlists path (adjust if needed)
WORDLISTS_DIR=/opt/thandev/wordlists
```

## services/thandev-brain/.env
```
ENVIRONMENT=development
DEBUG=false
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# RAG store
RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=thandev_rag

# Redis
REDIS_URL=redis://localhost:6379/0

# Embeddings
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Limits
BRAIN_MAX_STEPS=20
BRAIN_MAX_PARALLELISM=5
BRAIN_MAX_TOTAL_RUNTIME_SEC=3600
SESSION_MAX_STEPS=20
SESSION_MAX_RUNTIME_SEC=3600
SESSION_MAX_CONSECUTIVE_FAILURES=3
SESSION_NO_NEW_FINDINGS_ITERATIONS=3
ENRICH_FINDINGS_ENABLED=true
ENRICH_FINDINGS_MODEL=gpt-4o-mini
ENRICH_FINDINGS_TIMEOUT_SEC=30

# Backend URL for brain callbacks (if needed)
CORE_BACKEND_URL=http://localhost:8000
```

## frontend/.env.local
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

## Notes
- Ensure Postgres/Redis match the URLs above, or update the envs accordingly.
- If backend enforces runner auth, use the same `RUNNER_API_TOKEN` in backend and runner.
- Install scanner binaries locally (httpx, nuclei, nmap, sslscan, ffuf, dalfox, sqlmap); provide wordlists and nuclei templates locally.
- For Docker parity, you can also use `docker-compose up` (see `docker-compose.yml`) to run Postgres/Redis/Qdrant locally.




