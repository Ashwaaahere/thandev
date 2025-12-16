# Brain Service Setup with Virtual Environment

## Virtual Environment Setup

The brain service uses a virtual environment. Follow these steps:

### 1. Create and Activate Venv

```bash
cd services/thandev-brain

# Create venv (if not exists)
python3 -m venv venv
# OR
python3 -m venv .venv

# Activate venv
source venv/bin/activate  # Linux/Mac
# OR
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Make sure venv is activated (you should see (venv) in prompt)
pip install -r requirements.txt

# Install RAG dependencies
pip install qdrant-client sentence-transformers openai
```

### 3. Configure Environment

Create `.env` file:
```env
ENVIRONMENT=development
RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-key-here
```

### 4. Start Service

**Using the script:**
```bash
./start_brain.sh
```

**Or manually:**
```bash
# Make sure venv is activated!
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Verify Setup

```bash
# Check Python is using venv
which python  # Should point to venv/bin/python

# Test imports
python -c "import app.models; print('OK')"

# Test service
curl http://localhost:8001/health
```

## Common Issues

### "Module not found" errors
- Make sure venv is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Port 8001 already in use
- Change port in uvicorn command: `--port 8002`
- Update core backend config: `BRAIN_SERVICE_URL=http://localhost:8002`

### Qdrant connection errors
- Check Qdrant is running: `curl http://localhost:6333/health`
- Update QDRANT_URL in .env if using different port




