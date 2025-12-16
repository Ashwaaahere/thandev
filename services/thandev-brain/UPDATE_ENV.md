# Update .env File

## Current Issue
Your `.env` file has a placeholder DATABASE_URL:
```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

## Correct Configuration

Based on your `docker-compose.yml`, update the `.env` file to:

```env
# Database URL (for indexing script)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
```

## Full .env Template

Copy this to `services/thandev-brain/.env`:

```env
ENVIRONMENT=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=thandev_rag

EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database URL - UPDATE THIS!
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev

CORE_BACKEND_URL=http://localhost:8000
```

## Steps

1. **Start PostgreSQL:**
   ```bash
   cd /home/shree/ashwath/thandev
   docker-compose up -d postgres
   ```

2. **Update .env file** with the DATABASE_URL above

3. **Run indexing:**
   ```bash
   cd services/thandev-brain
   source venv/bin/activate
   python scripts/index_findings.py --limit 1000
   ```




