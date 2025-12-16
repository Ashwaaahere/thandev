# Phase 3 Implementation Summary

## Completed: /plan-scan with RAG + Rules

### What Was Implemented

1. **RAG Evidence Retrieval**
   - Multi-lane query system (latest findings, tech fingerprint, CVE templates, artifact summaries)
   - Evidence analysis (CVE signals, params fingerprint detection)
   - Graceful fallback if RAG unavailable

2. **Deterministic Rules**
   - **Rule 1:** Base tools based on scan level (basic/pro/advanced)
   - **Rule 2:** TLS endpoint → add sslscan/sslscan mode
   - **Rule 3:** Prior CVE signals → nuclei cve_fast confirm mode
   - **Rule 4:** Params-based app fingerprint → dalfox constrained mode
   - **Rule 5:** Tech stack-based tool selection (React/SPA → httpx)
   - **Rule 6:** Server error (5xx) → skip heavy network tools

3. **Plan Validation**
   - Tool/mode existence check (against catalog)
   - Params validation against JSON Schema
   - DAG acyclicity check (no circular dependencies)
   - Policy limit enforcement:
     - `BRAIN_MAX_STEPS` (default: 20)
     - `BRAIN_MAX_PARALLELISM` (default: 5)
     - `BRAIN_MAX_TOTAL_RUNTIME_SEC` (default: 3600)

4. **Timeline Calculation**
   - Parallel steps: max duration
   - Sequential steps: sum durations
   - Phase breakdown with parallel/sequential indicators

5. **Comprehensive Tests**
   - Empty plan validation
   - Invalid tool/mode detection
   - Unknown dependency detection
   - Cyclic dependency detection
   - Valid plan acceptance
   - Params validation (valid, invalid type, additional properties)
   - Timeline calculation (parallel, sequential, mixed)

### Example Plan Generation

**Request:**
```json
{
  "target_url": "https://example.com",
  "scan_level": "pro",
  "org_id": "org-123",
  "project_id": "project-456",
  "stack_info": {
    "http": {
      "status_code": 200,
      "headers": {"server": "nginx"}
    }
  }
}
```

**Response:**
```json
{
  "plan_id": "plan-uuid",
  "steps": [
    {
      "step_id": "step_1",
      "tool_id": "nuclei",
      "mode_id": "pro_web",
      "params": {},
      "depends_on": [],
      "reason": "Pro scan: Comprehensive vulnerability detection",
      "estimated_duration_sec": 600
    },
    {
      "step_id": "step_2",
      "tool_id": "nmap",
      "mode_id": "top_ports",
      "params": {},
      "depends_on": [],
      "reason": "Pro scan: Port and service discovery",
      "estimated_duration_sec": 300
    },
    {
      "step_id": "step_3",
      "tool_id": "sslscan",
      "mode_id": "standard",
      "params": {},
      "depends_on": [],
      "reason": "TLS endpoint detected: SSL/TLS configuration analysis required",
      "estimated_duration_sec": 300
    }
  ],
  "timeline": {
    "total_estimated_sec": 900,
    "phases": [
      {
        "phase": 1,
        "steps": ["step_1", "step_2", "step_3"],
        "estimated_duration_sec": 600,
        "parallel": true
      }
    ]
  },
  "metadata": {
    "generated_at": "2024-01-01T00:00:00Z",
    "scan_level": "pro",
    "target_url": "https://example.com",
    "rag_evidence_used": {
      "has_cve_signals": false,
      "has_params_fingerprint": false,
      "tech_fingerprint_detected": false
    }
  }
}
```

### Key Features

1. **RAG Integration**
   - Queries prior findings for the target/project
   - Detects technology stack
   - Identifies CVE signals
   - Detects params-based app patterns

2. **Rule-Based Logic**
   - Deterministic rules applied first (no LLM)
   - Rules are explainable and auditable
   - Rules can be extended easily

3. **Validation**
   - All plans validated before return
   - Catches errors early
   - Ensures plan is executable

4. **Timeline Accuracy**
   - Accounts for parallel execution
   - Accounts for sequential dependencies
   - Provides phase breakdown

### Testing

Run tests:
```bash
cd services/thandev-brain
pytest tests/test_plan_validation.py -v
```

Test coverage:
- Plan validation (empty, invalid tool/mode, dependencies, cycles)
- Params validation (valid, invalid, additional properties)
- Timeline calculation (parallel, sequential, mixed)

### Next Steps

Phase 4: Implement `/build-report-prompt` with evidence packing from RAG.




