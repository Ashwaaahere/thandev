# Thandev Runner Service

The runner service executes scan steps independently from the core API. It consumes step requests from Redis streams and executes tools, then publishes results back.

## Architecture

```
Brain Controller → Redis Stream (scan_step_requests)
                         ↓
                    Runner Service
                         ↓
                    Tool Execution
                         ↓
                    Findings Ingestion
                         ↓
                    Redis Stream (scan_step_results)
```

## Setup

1. **Install dependencies:**
   ```bash
   cd services/thandev-runner
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start runner:**
   ```bash
   ./start_runner.sh
   ```

## Configuration

- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `DATABASE_URL`: Database connection URL (for findings ingestion)
- `CONSUMER_GROUP`: Consumer group name (default: `runner-workers`)
- `CONSUMER_NAME`: Unique consumer name (default: hostname)
- `MAX_CONCURRENT_STEPS`: Maximum steps to process in parallel per worker (default: `5`)
- `MAX_INFLIGHT_PER_SESSION`: Maximum concurrent steps per session (default: `2`)

## Execution Adapter

The runner uses an execution adapter pattern to support different execution backends:

- **LocalAdapter** (default): Executes tools as subprocesses on the local machine
- **RemoteAdapter** (future): Executes tools via remote job service/containers

## Multi-Tenant Support

- Each step request includes `org_id` and `project_id`
- Findings are ingested with proper tenant context
- Database writes respect tenant isolation

## Scaling

### Multi-Worker Setup

Run multiple runner workers for horizontal scaling:

```bash
# Terminal 1: Worker 1
CONSUMER_NAME=worker-1 ./start_runner.sh

# Terminal 2: Worker 2
CONSUMER_NAME=worker-2 ./start_runner.sh

# Terminal 3: Worker 3
CONSUMER_NAME=worker-3 ./start_runner.sh
```

Workers use Redis Streams consumer groups for load balancing. Each worker:
- Processes steps in parallel (up to `MAX_CONCURRENT_STEPS`)
- Respects per-session concurrency limits (`MAX_INFLIGHT_PER_SESSION`)
- Automatically handles idempotency (duplicate steps are skipped)

### Parallel Execution

- **Within a worker**: Steps are processed concurrently using `asyncio.gather()`
- **Across workers**: Multiple workers consume from the same stream, distributing load
- **Per-session limits**: Each session can have at most `MAX_INFLIGHT_PER_SESSION` steps running simultaneously
- **Idempotency**: Steps are tracked by `(session_id, step_id)` to prevent duplicate execution

### Example: Starting 3 Workers

```bash
# Start 3 workers in separate terminals or use a process manager
for i in {1..3}; do
  CONSUMER_NAME=worker-$i ./start_runner.sh &
done
```

This enables true parallel execution across multiple users and sessions.



