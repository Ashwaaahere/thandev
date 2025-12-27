# Thandev Runner Service

## Scope

The Thandev Runner service is a separate service located in `services/thandev-runner/`. It executes security tool steps independently from the core backend API by consuming step requests from Redis streams and publishing results back.

## Architecture

```
Backend → Redis Stream (scan_step_requests)
                ↓
         Runner Service
                ↓
         Tool Execution
                ↓
         Findings Ingestion
                ↓
         Redis Stream (scan_step_results)
```

## Directory Structure

```
services/thandev-runner/
├── app/
│   ├── main.py              # Service entrypoint
│   ├── tasks.py             # Main worker loop and step processing
│   ├── config.py            # Settings
│   ├── executor.py          # Legacy tool execution adapter
│   ├── execution/            # Tool execution backends
│   │   ├── local.py         # LocalSubprocessBackend
│   │   ├── remote.py        # RemoteToolServiceBackend
│   │   └── selector.py      # Backend selection logic
│   ├── ingestion/            # Findings ingestion
│   │   └── direct_db.py     # Direct database writes
│   ├── queue/                # Redis stream management
│   │   └── streams.py       # Consumer/producer functions
│   └── concurrency/          # Concurrency control
│       └── slots.py          # Session slot management
├── requirements.txt
└── start_runner.sh           # Startup script
```

## Responsibilities

### 1. Consume Step Requests

**Source**: Redis Stream `scan_step_requests`

**Message Format**:
```json
{
  "session_id": "scan-session-id",
  "step_id": "step-1",
  "tool_id": "nuclei",
  "mode_id": "nuclei-fast",
  "target_ref": "https://example.com",
  "params": "{}",
  "depends_on": "[]",
  "org_id": "optional-org-id",
  "project_id": "project-id",
  "scan_job_id": "scan-job-id"
}
```

**Consumer Group**: `runner-workers` (configurable)

**Consumer Name**: Unique per worker (default: hostname)

### 2. Execute Tools

**Process**:
1. Parse step request
2. Check idempotency (skip if already executed)
3. Acquire session slot (respect per-session concurrency limits)
4. Select execution backend (local or remote)
5. Execute tool with parameters
6. Parse tool output
7. Release session slot

**Execution Backends**:
- **LocalSubprocessBackend**: Executes tools as subprocesses on local machine
- **RemoteToolServiceBackend**: Executes tools via HTTP requests to remote tool services

### 3. Ingest Findings

**Process**:
1. Parse tool output (JSON/XML)
2. Extract finding data
3. Write findings directly to database with tenant context
4. Update `ToolResult` records

**Location**: `app/ingestion/direct_db.py`

**Function**: `ingest_findings_direct_db(tool_output, scan_job_id, tool_name, db)`

### 4. Publish Results

**Destination**: Redis Stream `scan_step_results`

**Message Format**:
```json
{
  "session_id": "scan-session-id",
  "step_id": "step-1",
  "status": "completed" | "failed",
  "execution_time_sec": 120.5,
  "output": "tool output text",
  "error": "error message if failed"
}
```

## Tool Execution

### Supported Tools

- **nuclei**: Vulnerability scanner
- **nmap**: Network port scanner
- **httpx**: HTTP surface discovery
- **ffuf**: Web fuzzer
- **dalfox**: XSS scanner
- **sqlmap**: SQL injection tester
- **sslscan**: SSL/TLS analyzer

### Execution Adapters

**LocalAdapter** (default):
- Executes tools as subprocesses
- Runs on the same machine as runner service
- Requires tools to be installed and in PATH

**RemoteAdapter** (future):
- Executes tools via HTTP requests to remote tool services
- Useful for distributed execution
- Requires tool service endpoints

### Execution Backends

**LocalSubprocessBackend**:
- Location: `app/execution/local.py`
- Executes tools via `subprocess.run()`
- Captures stdout/stderr
- Handles timeouts

**RemoteToolServiceBackend**:
- Location: `app/execution/remote.py`
- Sends HTTP POST to tool service URL
- Waits for async response
- Handles errors and timeouts

## Concurrency Control

### Per-Session Limits

**Configuration**: `MAX_INFLIGHT_PER_SESSION` (default: 2)

**Purpose**: Prevent resource exhaustion by limiting concurrent steps per scan session

**Implementation**: Session slot management in `app/concurrency/slots.py`

**Process**:
1. Before executing step: Acquire session slot
2. If slot unavailable: Wait or skip (depending on configuration)
3. After execution: Release session slot

### Worker Parallelism

**Configuration**: `MAX_CONCURRENT_STEPS` (default: 5)

**Purpose**: Maximum steps to process in parallel per worker

**Implementation**: `asyncio.gather()` for parallel processing

**Example**: Worker can process 5 steps simultaneously, but each session limited to 2 concurrent steps

### Multi-Worker Scaling

**Pattern**: Multiple workers consume from same Redis stream using consumer groups

**Load Balancing**: Redis Streams automatically distributes messages across workers

**Example**:
```bash
# Terminal 1
CONSUMER_NAME=worker-1 ./start_runner.sh

# Terminal 2
CONSUMER_NAME=worker-2 ./start_runner.sh

# Terminal 3
CONSUMER_NAME=worker-3 ./start_runner.sh
```

## Idempotency

**Purpose**: Prevent duplicate step execution

**Implementation**: Tracks executed steps by `(session_id, step_id)`

**Process**:
1. Before execution: Check if step already executed
2. If executed: Skip and return cached result
3. If not executed: Execute and mark as executed

**Storage**: In-memory or Redis (depending on implementation)

## Multi-Tenant Support

**Tenant Context**:
- Each step request includes `org_id` and `project_id`
- Findings ingested with proper tenant context
- Database writes respect tenant isolation

**Database Queries**:
- All queries filter by `tenant_id` and `project_id`
- No cross-tenant data access

## Configuration

### Environment Variables

**Redis:**
- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)

**Database:**
- `DATABASE_URL`: Database connection URL (for findings ingestion)

**Consumer:**
- `CONSUMER_GROUP`: Consumer group name (default: `runner-workers`)
- `CONSUMER_NAME`: Unique consumer name (default: hostname)

**Concurrency:**
- `MAX_CONCURRENT_STEPS`: Maximum steps to process in parallel per worker (default: 5)
- `MAX_INFLIGHT_PER_SESSION`: Maximum concurrent steps per session (default: 2)

**Execution:**
- `EXECUTION_BACKEND`: `local` or `remote` (default: `local`)
- `TOOL_SERVICE_BASE_URL`: Base URL for remote tool services (if using remote backend)

### Configuration File

**Location**: `app/config.py`

**Settings Class**: `Settings` (Pydantic BaseSettings)

**Loads from**: Environment variables and `.env` file

## Running the Service

### Development

```bash
cd services/thandev-runner
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
CONSUMER_GROUP=runner-workers
CONSUMER_NAME=dev-worker
MAX_CONCURRENT_STEPS=5
MAX_INFLIGHT_PER_SESSION=2
EOF

# Start runner
./start_runner.sh
```

### Production

```bash
# Use process manager (systemd, supervisor, etc.)
# Or run in Docker container
docker run -d \
  -e REDIS_URL=redis://redis:6379/0 \
  -e DATABASE_URL=postgresql://... \
  thandev-runner
```

### Multi-Worker Setup

```bash
# Start multiple workers
for i in {1..3}; do
  CONSUMER_NAME=worker-$i ./start_runner.sh &
done
```

## Worker Loop

**Location**: `app/tasks.py`

**Function**: `run_worker_loop()`

**Process**:
1. Initialize logging
2. Enter infinite loop:
   - Consume step requests from Redis stream
   - Process messages in parallel (up to `MAX_CONCURRENT_STEPS`)
   - Wait for all tasks to complete
   - Repeat

**Error Handling**:
- Catches exceptions per message
- Logs errors
- Continues processing other messages
- Publishes error results for failed steps

## Integration with Backend

**Backend publishes step requests to**: Redis Stream `scan_step_requests`

**Backend consumes step results from**: Redis Stream `scan_step_results`

**Backend Location**: `backend/app/services/queue_manager.py` (if using Redis streams)

**Alternative**: Backend can also execute tools directly via Celery (current primary path)

## Dependencies

**Core:**
- `fastapi`: Web framework (if HTTP endpoints needed)
- `redis`: Redis client
- `sqlalchemy`: Database ORM
- `asyncio`: Async processing

**Tool Execution:**
- `subprocess`: Local tool execution
- `httpx`: HTTP client (for remote tool execution)

**See**: `requirements.txt` for full dependency list

