# Report Prompt Contract

## Overview

The `/build-report-prompt` endpoint returns a prompt package that the core backend uses to call OpenAI for report generation. The brain service does NOT generate the report JSON itself—it only provides the prompt structure.

## Request Format

```json
{
  "scan_job_id": "scan-123",
  "finding_ids": ["finding-1", "finding-2", "finding-3"],
  "artifact_refs": [
    {
      "id": "artifact-1",
      "tool_name": "nuclei",
      "file_path": "data/jobs/scan-123/nuclei_output.json",
      "scan_job_id": "scan-123",
      "summary": "Found 5 XSS vulnerabilities, 2 SQLi"
    }
  ],
  "org_id": "org-123",
  "project_id": "project-456"
}
```

## Response Format

```json
{
  "system_message": "You are a security report generator...",
  "user_content": {
    "scan_job_id": "scan-123",
    "findings": [
      {
        "id": "finding-1",
        "title": "XSS vulnerability",
        "description": "Cross-site scripting found in /page",
        "severity": "high",
        "cve_id": "CVE-2024-XXXX",
        "cvss_score": 7.5,
        "url": "https://target.com/page",
        "tool_name": "nuclei"
      }
    ],
    "findings_count": 3,
    "severity_breakdown": {
      "critical": 0,
      "high": 2,
      "medium": 1,
      "low": 0,
      "info": 0
    },
    "evidence": [
      {
        "type": "similar_finding",
        "source": "rag",
        "metadata": {...},
        "score": 0.85
      }
    ],
    "artifacts": [...],
    "instructions": "Generate a comprehensive security report..."
  },
  "report_json_schema": {
    "type": "object",
    "properties": {
      "executive_summary": {"type": "string"},
      "top_risks": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "title": {"type": "string"},
            "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
            "evidence_refs": {
              "type": "array",
              "items": {"type": "string"},
              "minItems": 1
            }
          },
          "required": ["title", "severity", "evidence_refs"],
          "additionalProperties": false
        }
      },
      "risk_score": {"type": "number", "minimum": 0, "maximum": 10},
      "findings_count": {"type": "integer"},
      "severity_breakdown": {
        "type": "object",
        "properties": {
          "critical": {"type": "integer"},
          "high": {"type": "integer"},
          "medium": {"type": "integer"},
          "low": {"type": "integer"},
          "info": {"type": "integer"}
        },
        "required": ["critical", "high", "medium", "low", "info"],
        "additionalProperties": false
      }
    },
    "required": ["executive_summary", "top_risks", "remediation_overview", "risk_score", "findings_count", "severity_breakdown"],
    "additionalProperties": false
  },
  "artifact_index": {
    "artifact-1": {
      "id": "artifact-1",
      "tool_name": "nuclei",
      "file_path": "data/jobs/scan-123/nuclei_output.json",
      "scan_job_id": "scan-123",
      "summary": "Found 5 XSS vulnerabilities, 2 SQLi"
    }
  },
  "metadata": {
    "scan_job_id": "scan-123",
    "finding_count": 3,
    "evidence_count": 5,
    "artifact_count": 1
  }
}
```

## Key Requirements

### 1. Evidence References

**Every finding in `top_risks` MUST have `evidence_refs`:**

```json
{
  "title": "XSS vulnerability",
  "severity": "high",
  "evidence_refs": ["artifact-1", "finding_1"]  // REQUIRED, minItems: 1
}
```

The `evidence_refs` must point to keys in the `artifact_index`.

### 2. Strict JSON Schema

The `report_json_schema` uses `additionalProperties: false` to ensure:
- No extra fields are added
- Structure matches exactly
- Compatible with OpenAI Structured Outputs

### 3. System Message Rules

The system message enforces:
- Do NOT invent findings
- All findings must cite evidence
- Follow schema exactly
- Risk score calculation rules

### 4. Evidence Items

Evidence items come from RAG retrieval:
- `similar_finding`: Similar findings from prior scans
- `cve_template`: CVE/template metadata
- `tech_fingerprint`: Technology stack info
- `artifact_summary`: Tool artifact summaries

### 5. Artifact Index

The `artifact_index` maps artifact IDs to metadata:
- Used by findings via `evidence_refs`
- Provides context for report generation
- Includes tool_name, file_path, summary

## Core Backend Usage

The core backend uses this prompt package like this:

```python
# 1. Call brain service
response = brain_client.build_report_prompt(
    scan_job_id=scan_job_id,
    finding_ids=finding_ids,
    artifact_refs=artifact_refs,
)

# 2. Call OpenAI with structured outputs
openai_response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": response.system_message},
        {"role": "user", "content": json.dumps(response.user_content)},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "security_report",
            "schema": response.report_json_schema.dict(),
        }
    }
)

# 3. Parse and store report
report_json = json.loads(openai_response.choices[0].message.content)
scan_job.summary = report_json
```

## Validation

The core backend should validate:
1. All `top_risks` have `evidence_refs`
2. All `evidence_refs` exist in `artifact_index`
3. Report matches schema (use JSON Schema validator)
4. Risk score is within 0-10 range
5. Severity breakdown matches findings count

## Example Report Output

```json
{
  "executive_summary": "Security scan detected 3 high-severity vulnerabilities requiring immediate attention.",
  "top_risks": [
    {
      "title": "XSS vulnerability in /page endpoint",
      "severity": "high",
      "cve_id": "CVE-2024-XXXX",
      "cvss_score": 7.5,
      "url": "https://target.com/page",
      "evidence_refs": ["artifact-1", "finding_1"],
      "description": "Cross-site scripting vulnerability detected...",
      "recommendation": "Sanitize user input and use Content Security Policy"
    }
  ],
  "remediation_overview": "1. Address XSS vulnerabilities immediately\n2. Review SQL injection findings\n3. Implement security headers",
  "risk_score": 7.5,
  "findings_count": 3,
  "severity_breakdown": {
    "critical": 0,
    "high": 2,
    "medium": 1,
    "low": 0,
    "info": 0
  },
  "scan_metadata": {
    "scan_level": "pro",
    "tools_used": ["nuclei", "nmap", "sslscan"],
    "scan_duration_sec": 1200
  }
}
```

## Error Handling

If RAG retrieval fails:
- Continue with findings only (no evidence)
- Log warning
- Return prompt package without evidence items

If findings cannot be loaded:
- Return error response
- Do not generate prompt package

## Future Enhancements

1. **Multi-modal evidence**: Include screenshots, network diagrams
2. **Evidence ranking**: Rank evidence by relevance score
3. **Template-based prompts**: Use different prompts for different scan levels
4. **Evidence summarization**: Pre-summarize evidence for token efficiency




