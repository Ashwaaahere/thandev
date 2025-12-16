# Thandev Brain Service API Documentation

## Overview

The Thandev Brain Service is a RAG-powered service that generates scan plans and report prompt packages. It does NOT execute tools or generate reports directly—it only provides structured plans and prompts.

## Base URL

```
http://localhost:8001/v1
```

## Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "thandev-brain",
  "version": "1.0.0"
}
```

### GET /catalog

Get the tool catalog with all available tools and modes.

**Response:**
```json
{
  "tools": [
    {
      "tool_id": "nuclei",
      "name": "Nuclei Vulnerability Scanner",
      "description": "Fast vulnerability scanner using community-driven templates",
      "allowed_target_types": ["http", "https"],
      "modes": [
        {
          "mode_id": "basic_web",
          "name": "Basic Web Scan",
          "description": "Quick scan for common vulnerabilities",
          "params_schema": {
            "type": "object",
            "properties": {
              "tags": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["cves", "misconfig"]
              }
            },
            "additionalProperties": false
          },
          "constraints": {
            "max_timeout_sec": 600
          }
        }
      ]
    }
  ],
  "metadata": {
    "version": "1.0.0"
  }
}
```

### POST /plan-scan

Generate a scan plan based on target information and scan level.

**Request:**
```json
{
  "target_url": "https://example.com",
  "scan_level": "pro",
  "org_id": "org-123",
  "project_id": "project-456",
  "stack_info": {
    "target_url": "https://example.com",
    "scan_level": "pro",
    "http": {
      "status_code": 200,
      "headers": {
        "server": "nginx",
        "content_type": "text/html"
      }
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
    }
  ],
  "timeline": {
    "total_estimated_sec": 600,
    "phases": [
      {
        "phase": 1,
        "steps": ["step_1", "step_2"]
      }
    ]
  },
  "metadata": {
    "generated_at": "2024-01-01T00:00:00Z",
    "scan_level": "pro",
    "target_url": "https://example.com"
  }
}
```

### POST /build-report-prompt

Build a prompt package for OpenAI report generation.

**Request:**
```json
{
  "scan_job_id": "scan-123",
  "finding_ids": ["finding-1", "finding-2"],
  "artifact_refs": [
    {
      "tool_name": "nuclei",
      "file_path": "data/jobs/scan-123/nuclei_output.json"
    }
  ],
  "org_id": "org-123",
  "project_id": "project-456"
}
```

**Response:**
```json
{
  "system_message": "You are a security report generator...",
  "user_content": {
    "scan_job_id": "scan-123",
    "findings": [
      {
        "id": "finding-1",
        "title": "XSS vulnerability",
        "severity": "high",
        "url": "https://example.com/page",
        "evidence_refs": ["artifact-1"]
      }
    ],
    "evidence": [],
    "artifacts": []
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
            "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]}
          },
          "required": ["title", "severity"],
          "additionalProperties": false
        }
      },
      "risk_score": {"type": "number"},
      "findings_count": {"type": "integer"}
    },
    "required": ["executive_summary", "top_risks", "risk_score"],
    "additionalProperties": false
  },
  "artifact_index": {},
  "metadata": {
    "scan_job_id": "scan-123",
    "finding_count": 2
  }
}
```

## Constraints

1. **Brain does NOT output raw shell commands** - Only returns `tool_id`, `mode_id`, `params`, ordering, dependencies, timeline, and reason.

2. **Brain does NOT execute tools** - The core backend dispatches steps to the runner.

3. **Brain does NOT generate report JSON** - It only returns prompt packages. The core backend calls OpenAI.

4. **All responses are schema-validated** - Uses `additionalProperties: false` where possible.

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `400 Bad Request`: Invalid request (validation error)
- `500 Internal Server Error`: Server error

Error response format:
```json
{
  "error": "Error type",
  "message": "Detailed error message"
}
```




