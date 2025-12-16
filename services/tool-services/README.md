# Tool Services

Tool microservices for executing security scanning tools in isolated containers/services.

## Architecture

Each tool runs in its own container/service:
- `nuclei-service`: Executes Nuclei scans
- `ffuf-service`: Executes FFuF directory brute forcing
- (Future: `nmap-service`, `httpx-service`, etc.)

## Service Interface

All tool services implement the same HTTP interface:

### POST `/run`

Execute a tool step.

**Request:**
```json
{
  "session_id": "uuid",
  "step_id": "uuid",
  "tool_id": "nuclei",
  "mode_id": "pro_web",
  "target": "http://example.com",
  "params": {},
  "org_id": "string",
  "project_id": "string",
  "scan_job_id": "uuid",
  "scope": {}
}
```

**Response:**
```json
{
  "success": true,
  "tool_name": "nuclei",
  "output": "tool stdout/stderr",
  "exit_code": 0,
  "execution_time": 45.67,
  "artifact_refs": ["s3://bucket/artifacts/nuclei_output.json"],
  "findings": [],  // Optional: normalized findings
  "error": null,
  "baseline": null  // For ffuf: baseline filter data
}
```

## Implementation

Each service:
1. Validates tool_id/mode_id/params against catalog
2. Executes tool with safe flags
3. Writes output to shared storage (S3, GCS, or local filesystem)
4. Returns artifact URLs or IDs
5. Optionally returns normalized findings

## Deployment

Services can be deployed as:
- Docker containers
- Cloud Run Jobs
- ECS tasks
- Kubernetes jobs

## Configuration

- `TOOL_SERVICE_BASE_URL`: Base URL for tool services (e.g., "http://tool-nuclei:8000")
- `REMOTE_TOOLS`: Comma-separated list of tools to use remote services (e.g., "nuclei,ffuf")

