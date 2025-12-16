# Next Steps - Post-Implementation

## Completed ✅

All 5 phases of the brain service implementation are complete:
- Phase 0: Repository audit
- Phase 1: Brain service skeleton
- Phase 2: RAG foundation
- Phase 3: /plan-scan with RAG + rules
- Phase 4: /build-report-prompt with evidence
- Phase 5: Core backend integration

## Immediate Next Steps

### 1. Index Existing Findings into RAG Store

Populate the RAG store with existing findings for better planning and reporting:

```bash
cd services/thandev-brain
source venv/bin/activate

# Index all findings (limit 1000)
python scripts/index_findings.py --limit 1000

# Index findings for specific project
python scripts/index_findings.py --project-id <project_id> --limit 500

# Index findings for specific org
python scripts/index_findings.py --org-id <org_id> --limit 1000
```

**Note:** Make sure `DATABASE_URL` in brain service `.env` points to the same database as core backend.

### 2. Test End-to-End Integration

**Test Planning:**
```bash
# Create a scan via API
curl -X POST http://localhost:8000/api/v1/scans \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Tenant-Id: <tenant_id>" \
  -H "X-Thandev-User-Id: <user_id>" \
  -d '{
    "project_id": "<project_id>",
    "scan_level": "pro"
  }'

# Check logs to verify brain service is called
# Verify plan is generated and tools execute
```

**Test Report Generation:**
```bash
# After scan completes, check that report was generated
# Verify brain service was called for prompt package
# Verify OpenAI was called with the prompt package
```

### 3. Add Server-Side Validation Gates

Implement validation in core backend before tool execution:

**File:** `backend/app/services/scan_orchestrator.py`

Add after plan conversion:
```python
# Validate tool_id/mode_id exists in local catalog
from app.core.tool_matrix import is_tool_enabled_for_level

for step in brain_plan.get("steps", []):
    tool_id = step.get("tool_id")
    if not is_tool_enabled_for_level(tool_id, scan_job.scan_level):
        logger.warning(f"Tool {tool_id} not allowed for level {scan_job.scan_level}, skipping")
        # Remove from plan or raise error
```

### 4. Sync Tool Catalog

Create a mechanism to sync catalog from brain to core backend:

**Option A: HTTP endpoint**
- Brain service exposes `/v1/catalog`
- Core backend fetches on startup or periodically

**Option B: Shared file**
- Catalog JSON in shared location
- Both services read from same file

### 5. Monitor and Tune

**Metrics to Track:**
- Brain service call latency
- RAG retrieval quality (relevance scores)
- Plan validation failures
- Report generation success rate
- Fallback usage frequency

**Tuning:**
- Adjust RAG retrieval `top_k` based on results
- Fine-tune embedding model if needed
- Adjust rule thresholds based on scan results

## Future Enhancements

### 1. Enhanced RAG Retrieval
- Hybrid search (vector + keyword)
- Reranking with cross-encoder
- Temporal filtering (weight recent findings)

### 2. Advanced Planning
- Multi-wave planning with feedback loops
- Dynamic tool selection based on intermediate results
- Cost-aware planning (time/API costs)

### 3. Report Quality
- Evidence quality scoring
- Automatic evidence validation
- Multi-modal evidence (screenshots, diagrams)

### 4. Performance
- Cache frequently used plans
- Batch RAG queries
- Async indexing pipeline

## Testing Checklist

- [ ] Brain service starts without errors
- [ ] Qdrant connection works
- [ ] Catalog endpoint returns valid catalog
- [ ] Plan generation works for all scan levels
- [ ] Plan validation catches invalid tools/modes
- [ ] Report prompt generation loads findings correctly
- [ ] Core backend calls brain service successfully
- [ ] Fallback works when brain service unavailable
- [ ] RAG indexing script works
- [ ] End-to-end scan flow works with brain service

## Troubleshooting

### Brain Service Not Called
- Check `BRAIN_SERVICE_ENABLED=true` in backend `.env`
- Check `BRAIN_SERVICE_URL` is correct
- Check brain service is running: `curl http://localhost:8001/health`
- Check logs for connection errors

### RAG Retrieval Returns Empty
- Index findings first: `python scripts/index_findings.py`
- Check Qdrant is running
- Check embedding provider is configured
- Verify findings exist in database

### Plan Validation Fails
- Check catalog has the tool/mode
- Verify params match params_schema
- Check for circular dependencies
- Verify policy limits are reasonable

## Documentation

All documentation is in `docs/`:
- `REPO_MAP.md` - Repository structure
- `CURRENT_SCAN_FLOW.md` - Scan flow
- `BRAIN_API.md` - API reference
- `RAG_DESIGN.md` - RAG architecture
- `REPORT_PROMPT_CONTRACT.md` - Report contract
- `BRAIN_INTEGRATION.md` - Integration guide
- `FINAL_SETUP_GUIDE.md` - Setup instructions

## Ready for Production

The brain service is ready for testing and gradual rollout:
1. Start with development/testing
2. Monitor performance and errors
3. Tune RAG retrieval parameters
4. Gradually enable for production scans




