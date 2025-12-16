# Brain Service Integration Guide

## Overview

This document describes how the core backend integrates with the Thandev Brain Service for RAG-powered scan planning and report generation.

## Architecture

```
Core Backend (FastAPI)
    │
    ├─→ Brain Client (brain_client.py)
    │       │
    │       ├─→ POST /v1/plan-scan (for scan planning)
    │       └─→ POST /v1/build-report-prompt (for report generation)
    │
    └─→ OpenAI Client (openai_client.py)
            └─→ Uses prompt package from brain for report generation
```

## Configuration

Add to `backend/.env`:

```env
# Brain Service
BRAIN_SERVICE_URL=http://localhost:8001
BRAIN_SERVICE_ENABLED=true

# OpenAI (required for report generation)
OPENAI_API_KEY=your-openai-api-key
```

## Integration Points

### 1. Scan Planning

**Location:** `backend/app/services/scan_orchestrator.py::run_scan_for_job()`

**Flow:**
1. Core backend calls `brain_client.create_plan()`
2. Brain service returns plan with steps (tool_id, mode_id, params, dependencies)
3. Core backend converts brain plan format to orchestrator format
4. Falls back to legacy planner if brain service unavailable

**Code:**
```python
from app.services.brain_client import get_brain_client

brain_client = get_brain_client()
brain_plan = await brain_client.create_plan(
    target_url=target_url,
    scan_level=scan_level,
    org_id=org_id,
    project_id=project_id,
    stack_info=stack_info,
)

# Convert to orchestrator format
# Brain: {steps: [{tool_id, mode_id, params, depends_on}]}
# Orchestrator: {waves: [{tools: [{name, config}]}]}
```

**Validation Gates:**
- Verify tool_id/mode_id exists in local catalog copy (TODO: sync catalog)
- Enforce scope rules (project belongs to org)
- Enforce quotas (monthly scans, concurrent scans)

### 2. Report Generation

**Location:** `backend/app/services/scan_orchestrator.py::run_scan_for_job()`

**Flow:**
1. Core backend collects findings and artifact refs
2. Calls `brain_client.build_report_prompt()`
3. Brain service returns prompt package (system message, user content, JSON schema)
4. Core backend calls OpenAI with structured outputs using the prompt package
5. Parses and stores report JSON
6. Falls back to basic report if brain service unavailable

**Code:**
```python
from app.services.brain_client import get_brain_client
from app.services.ai.openai_client import get_openai_client

# Get prompt package from brain
prompt_package = await brain_client.build_report_prompt(
    scan_job_id=scan_job_id,
    finding_ids=finding_ids,
    artifact_refs=artifact_refs,
    org_id=org_id,
    project_id=project_id,
)

# Call OpenAI with structured outputs
openai_client = get_openai_client()
response = await openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": prompt_package["system_message"]},
        {"role": "user", "content": json.dumps(prompt_package["user_content"])},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "security_report",
            "schema": prompt_package["report_json_schema"],
        }
    },
)

# Parse and store
report_json = json.loads(response.choices[0].message.content)
scan_job.summary = report_json
```

**Validation Gates:**
- Verify all `top_risks` have `evidence_refs`
- Verify all `evidence_refs` exist in `artifact_index`
- Validate report matches JSON schema
- Verify risk_score is within 0-10 range

## Fallback Behavior

### Planning Fallback

If brain service is disabled or unavailable:
1. Falls back to legacy `plan_scan()` (rule-based)
2. If that fails, uses `tool_matrix` directly

### Report Generation Fallback

If brain service is disabled or unavailable:
1. Falls back to `generate_basic_report()` (rule-based, no LLM)
2. If that fails, uses minimal summary format

## Validation Gates

### Server-Side Validation (TODO: Implement)

**Before Tool Execution:**
```python
# Verify tool_id/mode_id exists in local catalog copy
from app.core.tool_matrix import is_tool_enabled_for_level

if not is_tool_enabled_for_level(step.tool_id, scan_level):
    raise ValueError(f"Tool {step.tool_id} not allowed for level {scan_level}")

# Enforce scope rules
if project.tenant_id != org_id:
    raise ValueError("Project does not belong to organization")

# Enforce quotas
from app.core.plans import get_plan_limits
limits = get_plan_limits(tenant)
if monthly_scans >= limits["max_scans_per_month"]:
    raise ValueError("Monthly scan quota exceeded")
```

**After Report Generation:**
```python
# Validate report structure
import jsonschema
jsonschema.validate(instance=report_json, schema=prompt_package["report_json_schema"])

# Verify evidence references
for risk in report_json.get("top_risks", []):
    if not risk.get("evidence_refs"):
        raise ValueError(f"Finding {risk.get('title')} missing evidence_refs")
    
    for ref in risk["evidence_refs"]:
        if ref not in prompt_package["artifact_index"]:
            raise ValueError(f"Evidence ref {ref} not found in artifact_index")
```

## Error Handling

### Brain Service Unavailable

- Logs warning
- Falls back to legacy implementations
- Scan continues without brain features

### Invalid Plan Response

- Logs error
- Falls back to tool_matrix
- Scan continues with basic tools

### Invalid Report Response

- Logs error
- Falls back to basic report
- Scan completes with rule-based summary

## Testing

### Test Brain Service Integration

```python
# Test planning
from app.services.brain_client import get_brain_client

brain_client = get_brain_client()
plan = await brain_client.create_plan(
    target_url="https://example.com",
    scan_level="pro",
    stack_info={"http": {"status_code": 200}},
)

assert "steps" in plan
assert len(plan["steps"]) > 0

# Test report prompt
prompt = await brain_client.build_report_prompt(
    scan_job_id="test-scan",
    finding_ids=["finding-1", "finding-2"],
)

assert "system_message" in prompt
assert "user_content" in prompt
assert "report_json_schema" in prompt
```

## Deployment

### Development

1. Start brain service:
   ```bash
   cd services/thandev-brain
   uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```

2. Start core backend:
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### Production

1. Add brain service to `docker-compose.yml`
2. Set `BRAIN_SERVICE_URL` to production URL
3. Ensure brain service is accessible from core backend
4. Monitor brain service health

## Monitoring

### Metrics to Track

- Brain service availability (health checks)
- Planning request latency
- Report prompt generation latency
- Fallback rate (brain unavailable)
- Plan validation failures
- Report validation failures

### Logging

- All brain service calls logged
- Fallback events logged with warnings
- Validation failures logged with errors

## Future Enhancements

1. **Catalog Sync**: Sync tool catalog from brain to core backend
2. **Caching**: Cache plans and prompts for similar targets
3. **Retry Logic**: Retry brain service calls with exponential backoff
4. **Circuit Breaker**: Circuit breaker pattern for brain service
5. **Metrics**: Prometheus metrics for brain service integration




