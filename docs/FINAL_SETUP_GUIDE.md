# Final Setup Guide - Thandev Brain Service

## Quick Start Checklist

### 1. Fix Syntax Errors ✅
- Fixed: `await` outside async function in `scan_orchestrator.py`
- Changed to use `loop.run_until_complete()` for brain client calls

### 2. Start Qdrant

**Option A: Check if already running**
```bash
curl http://localhost:6333/health
```

**Option B: Start Qdrant (if not running)**
```bash
# If port 6333 is already in use, check what's using it:
sudo lsof -i :6333

# Or use a different port:
docker run -d -p 6334:6333 --name qdrant qdrant/qdrant:latest
# Then update BRAIN_SERVICE .env: QDRANT_URL=http://localhost:6334
```

**Option C: Stop existing Qdrant and restart**
```bash
docker ps | grep qdrant  # Find container ID
docker stop <container_id>
docker rm <container_id>
docker run -d -p 6333:6333 qdrant/qdrant:latest
```

### 3. Setup Brain Service Virtual Environment

```bash
cd services/thandev-brain

# Create venv if not exists
python3 -m venv venv  # or .venv

# Activate venv
source venv/bin/activate  # Linux/Mac
# OR
.venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install RAG dependencies
pip install qdrant-client sentence-transformers openai
```

### 4. Configure Brain Service

Create `services/thandev-brain/.env`:
```env
ENVIRONMENT=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=thandev_rag

EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=5V2HVXAboHT2JhRcXq2aKGowsrIotWU3jiGf7w8VuEB-vpaHivtoHI9U-95OCxlwrQUCUkWF7nT3BlbkFJn9zXC9oFMtsd8N_z3GuntRh-pUIyxhXhSIYOt-aIGixyTXnhKmhTqf1_zJkwnbV3S5AbGY0LIA
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

BRAIN_MAX_STEPS=20
BRAIN_MAX_PARALLELISM=5
BRAIN_MAX_TOTAL_RUNTIME_SEC=3600
```

### 5. Start Brain Service

**Using the script (recommended):**
```bash
cd services/thandev-brain
source venv/bin/activate  # Activate venv first
./start_brain.sh
```

**Or manually:**
```bash
cd services/thandev-brain
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 6. Configure Core Backend

Add to `backend/.env`:
```env
# Brain Service Integration
BRAIN_SERVICE_URL=http://localhost:8001
BRAIN_SERVICE_ENABLED=true

# OpenAI (for report generation)
OPENAI_API_KEY=5V2HVXAboHT2JhRcXq2aKGowsrIotWU3jiGf7w8VuEB-vpaHivtoHI9U-95OCxlwrQUCUkWF7nT3BlbkFJn9zXC9oFMtsd8N_z3GuntRh-pUIyxhXhSIYOt-aIGixyTXnhKmhTqf1_zJkwnbV3S5AbGY0LIA
```

### 7. Verify Everything Works

**Check all services:**
```bash
./check_services.sh
```

**Test brain service:**
```bash
# Health check
curl http://localhost:8001/health

# Get catalog
curl http://localhost:8001/v1/catalog | python3 -m json.tool

# Test planning
curl -X POST http://localhost:8001/v1/plan-scan \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "scan_level": "pro"
  }' | python3 -m json.tool
```

**Test core backend:**
```bash
curl http://localhost:8000/health
```

## Troubleshooting

### Qdrant Port Already Allocated

**Solution 1: Use existing Qdrant**
```bash
# Check what's on port 6333
curl http://localhost:6333/health

# If Qdrant is running, just use it
# Update .env if needed: QDRANT_URL=http://localhost:6333
```

**Solution 2: Use different port**
```bash
docker run -d -p 6334:6333 --name qdrant qdrant/qdrant:latest
# Update .env: QDRANT_URL=http://localhost:6334
```

**Solution 3: Stop and restart**
```bash
docker ps -a | grep qdrant
docker stop <container_id>
docker rm <container_id>
docker run -d -p 6333:6333 qdrant/qdrant:latest
```

### Brain Service Import Errors

If you see import errors, make sure:
1. Virtual environment is activated
2. Dependencies are installed: `pip install -r requirements.txt`
3. You're running from `services/thandev-brain/` directory

### Core Backend Syntax Errors

The async issue has been fixed. If you still see errors:
1. Restart the backend server
2. Check that `loop.run_until_complete()` is used (not `await`)
3. Verify `loop` variable exists in scope

## Service Startup Order

1. **Qdrant** (if using Qdrant for RAG)
2. **Brain Service** (port 8001)
3. **Core Backend** (port 8000)
4. **Redis** (for Celery)
5. **PostgreSQL** (for database)

## Testing the Integration

### 1. Test Brain Service Directly

```bash
# Health
curl http://localhost:8001/health

# Catalog
curl http://localhost:8001/v1/catalog

# Plan scan
curl -X POST http://localhost:8001/v1/plan-scan \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "scan_level": "pro",
    "stack_info": {
      "http": {"status_code": 200}
    }
  }'
```

### 2. Test Core Backend Integration

Create a scan via the API and verify:
- Brain service is called for planning
- Plan is converted to orchestrator format
- Tools execute based on brain plan
- Report generation uses brain prompt package

## Next Steps

1. **Index Existing Data**: Populate RAG store with prior findings
2. **Monitor**: Watch logs for brain service calls
3. **Tune**: Adjust RAG retrieval parameters based on results
4. **Validate**: Ensure all plans pass validation gates

## Files Modified

- `backend/app/services/scan_orchestrator.py` - Fixed async calls
- `backend/app/services/brain_client.py` - Brain service client
- `backend/app/core/config.py` - Added brain service config
- `services/thandev-brain/` - Complete brain service implementation

All syntax errors should now be resolved!




