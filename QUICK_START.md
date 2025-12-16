# Quick Start - Thandev Brain Service

## ✅ All Issues Fixed!

### Syntax Errors Fixed
- ✅ Fixed `await` outside async function in `scan_orchestrator.py`
- ✅ Changed to `loop.run_until_complete()` for brain client calls
- ✅ All Python files pass syntax check

## Start Services

### 1. Start Qdrant (if not running)

```bash
# Check if already running
curl http://localhost:6333/health

# If not running, start it
docker run -d -p 6333:6333 qdrant/qdrant:latest

# If port is in use, use different port:
docker run -d -p 6334:6333 --name qdrant qdrant/qdrant:latest
# Then update .env: QDRANT_URL=http://localhost:6334
```

### 2. Start Brain Service (with venv)

```bash
cd services/thandev-brain

# Activate your venv
source venv/bin/activate  # or .venv/bin/activate

# Install dependencies (if not done)
pip install -r requirements.txt

# Create .env file (if not exists)
cat > .env << EOF
ENVIRONMENT=development
RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=5V2HVXAboHT2JhRcXq2aKGowsrIotWU3jiGf7w8VuEB-vpaHivtoHI9U-95OCxlwrQUCUkWF7nT3BlbkFJn9zXC9oFMtsd8N_z3GuntRh-pUIyxhXhSIYOt-aIGixyTXnhKmhTqf1_zJkwnbV3S5AbGY0LIA
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EOF

# Start service
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 3. Configure Core Backend

Add to `backend/.env`:
```env
BRAIN_SERVICE_URL=http://localhost:8001
BRAIN_SERVICE_ENABLED=true
OPENAI_API_KEY=5V2HVXAboHT2JhRcXq2aKGowsrIotWU3jiGf7w8VuEB-vpaHivtoHI9U-95OCxlwrQUCUkWF7nT3BlbkFJn9zXC9oFMtsd8N_z3GuntRh-pUIyxhXhSIYOt-aIGixyTXnhKmhTqf1_zJkwnbV3S5AbGY0LIA
```

### 4. Test Everything

```bash
# Test brain service
curl http://localhost:8001/health
curl http://localhost:8001/v1/catalog

# Test core backend
curl http://localhost:8000/health

# Test planning
curl -X POST http://localhost:8001/v1/plan-scan \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com", "scan_level": "pro"}'
```

## Verification

All syntax errors are fixed! The code should now:
- ✅ Import without syntax errors
- ✅ Use `loop.run_until_complete()` instead of `await` in sync functions
- ✅ Work with brain service integration

## Next Steps

1. Start all services
2. Test a scan creation via API
3. Verify brain service is called for planning
4. Check report generation uses brain prompt package




