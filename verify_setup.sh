#!/bin/bash
# Verify Thandev Brain Service setup

echo "=== Verifying Thandev Brain Service Setup ==="
echo ""

# Check syntax errors
echo "1. Checking for syntax errors..."
cd backend
if python3 -m py_compile app/services/scan_orchestrator.py app/services/brain_client.py app/core/config.py 2>/dev/null; then
    echo "   ✓ No syntax errors in core backend files"
else
    echo "   ✗ Syntax errors found"
    exit 1
fi
cd ..

# Check brain service files
echo "2. Checking brain service files..."
cd services/thandev-brain
if python3 -m py_compile app/main.py app/api/v1.py app/models.py 2>/dev/null; then
    echo "   ✓ No syntax errors in brain service files"
else
    echo "   ✗ Syntax errors found"
    exit 1
fi
cd ../..

# Check Qdrant
echo "3. Checking Qdrant..."
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "   ✓ Qdrant is running on port 6333"
else
    echo "   ⚠ Qdrant not running (will use fallback if needed)"
fi

# Check brain service
echo "4. Checking brain service..."
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "   ✓ Brain service is running on port 8001"
else
    echo "   ⚠ Brain service not running"
    echo "   Start with: cd services/thandev-brain && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8001"
fi

# Check core backend
echo "5. Checking core backend..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✓ Core backend is running on port 8000"
else
    echo "   ⚠ Core backend not running"
fi

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Next steps:"
echo "1. Start Qdrant: docker run -d -p 6333:6333 qdrant/qdrant:latest"
echo "2. Start brain service: cd services/thandev-brain && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8001"
echo "3. Start core backend: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "All syntax errors have been fixed! ✅"




