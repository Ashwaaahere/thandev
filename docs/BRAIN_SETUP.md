# Thandev Brain Service - Setup Guide

## Quick Start

### 1. Install Dependencies

```bash
cd services/thandev-brain
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and set your configuration:

```env
# For OpenAI embeddings (optional, but recommended for better quality)
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-api-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# For Qdrant (default, recommended)
RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
```

### 3. Start Qdrant (if using Qdrant)

**Option A: Docker**
```bash
docker run -p 6333:6333 qdrant/qdrant:latest
```

**Option B: Docker Compose**
Add to your `docker-compose.yml`:
```yaml
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

### 4. Run Brain Service

```bash
cd services/thandev-brain
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 5. Test

```bash
# Health check
curl http://localhost:8001/health

# Get catalog
curl http://localhost:8001/v1/catalog
```

## Configuration Options

### RAG Storage

**Qdrant (Recommended):**
- Fast, scalable vector database
- Easy to deploy
- Good for production

**PostgreSQL + pgvector:**
- Uses existing database
- Good for single-database deployments
- Requires pgvector extension

### Embedding Provider

**Sentence Transformers (Default):**
- Model: `all-MiniLM-L6-v2`
- Runs locally, no API calls
- Fast and free
- Good quality for most use cases

**OpenAI:**
- Model: `text-embedding-3-small`
- Requires API key
- Higher quality embeddings
- Better for complex queries

## Setting Up OpenAI API Key

1. Get your API key from https://platform.openai.com/api-keys
2. Add to `.env`:
   ```env
   OPENAI_API_KEY=sk-your-key-here
   EMBEDDING_PROVIDER=openai
   ```
3. Restart the service

**Note:** The API key you provided should be set in the `.env` file, not hardcoded in the code.

## Docker Compose Integration

Add to your main `docker-compose.yml`:

```yaml
  brain:
    build: ./services/thandev-brain
    ports:
      - "8001:8001"
    environment:
      RAG_STORE_TYPE: qdrant
      QDRANT_URL: http://qdrant:6333
      EMBEDDING_PROVIDER: openai
      OPENAI_API_KEY: ${OPENAI_API_KEY}
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

## Troubleshooting

### Qdrant Connection Error

```bash
# Check if Qdrant is running
curl http://localhost:6333/health

# Start Qdrant if not running
docker run -p 6333:6333 qdrant/qdrant:latest
```

### OpenAI API Key Error

```bash
# Check if key is set
echo $OPENAI_API_KEY

# Or check .env file
cat services/thandev-brain/.env | grep OPENAI_API_KEY
```

### Import Errors

```bash
# Install missing dependencies
pip install qdrant-client sentence-transformers openai
```

## Next Steps

1. **Test the service:** Use the examples in `BRAIN_API.md`
2. **Integrate with core backend:** See Phase 5 implementation
3. **Index documents:** Use the ingestion utilities to populate RAG store




