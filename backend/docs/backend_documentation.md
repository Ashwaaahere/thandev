# Thandev Backend Documentation

## 1. Executive Summary

This document provides a complete overview of the Thandev Backend, a sophisticated security intelligence platform designed for automated vulnerability scanning. The system leverages a microservices-like architecture (within a monolith) using FastAPI for the REST API, Celery for asynchronous task orchestration, and Redis for message passing and caching.

## 2. System Architecture

The backend is built on a robust technology stack:

-   **Web Framework**: FastAPI (High-performance, async Python framework).
-   **Database**: PostgreSQL (Production) / SQLite (Development).
-   **ORM**: SQLAlchemy (Database abstraction).
-   **Migrations**: Alembic.
-   **Task Queue**: Celery (Asynchronous background jobs).
-   **Message Broker**: Redis (Used for Celery and inter-service communication).
-   **Scanning Tools**: Integration with industry-standard tools (Nuclei, Dalfox, Nmap, SSLScan, etc.).

### High-Level Data Flow

1.  **User Request**: A user submits a scan request via the API (e.g., `POST /api/scans`).
2.  **Validation**: The API validates the request, checks quotas, and verifies permissions (Project/Tenant).
3.  **Orchestration**: The request is passed to the `ScanOrchestrator`.
    -   If "Brain" service is enabled, a session is started for closed-loop autonomous scanning.
    -   Otherwise, a Celery task or Runner job is queued.
4.  **Execution**:
    -   **Celery Workers**: Pick up the scan job.
    -   **Tool Execution**: The `ToolExecutor` runs configured tools (e.g., Nuclei) against the target.
5.  **Ingestion**: Output files from tools are parsed by `FindingsIngestor`.
6.  **Persistence**: Findings are saved to the PostgreSQL database.
7.  **Notification**: The user is notified of completion (via Webhooks/Email if configured).

## 3. Codebase Structure

The codebase follows a clean, modular structure in `backend/app`:

-   **`api/`**: API Routers defining endpoints (REST interface).
    -   `scans.py`: Scan management.
    -   `projects.py`: Project management.
    -   `findings.py`: Vulnerability retrieval.
    -   `tenants.py`, `users.py`: Multi-tenancy and authentication.
-   **`core/`**: Core configuration and utilities.
    -   `config.py`: Environment settings.
    -   `database.py`: DB session management.
    -   `security.py`: Authentication logic.
-   **`models/`**: SQLAlchemy database models.
    -   `scan.py`, `finding.py`, `project.py`, `user.py`, `tenant.py`.
-   **`schemas/`**: Pydantic models for request/response validation.
-   **`services/`**: Business logic and core services.
    -   `scan_orchestrator.py`: Manages the lifecycle of a scan.
    -   `tools.py`: Wrappers for executing security tools (Nuclei, Nmap, etc.).
    -   `findings_ingestor.py`: Parsers for tool outputs.
    -   `pdf_reports.py`: Generation of scan reports.
    -   `brain_client.py`: Interface to the AI "Brain" service.
-   **`tasks/`**: Celery task definitions.

## 4. Key Components Detail

### 4.1 Scan Orchestrator (`app/services/scan_orchestrator.py`)
This is the heart of the system. It handles:
-   Queueing scans logic (supporting user-specific queues).
-   Running individual tools in parallel (`_run_single_tool`).
-   Managing file I/O for tool outputs.
-   Triggering ingestion upon tool completion.
-   Handling timeouts and failures gracefully.

### 4.2 Tool Executor (`app/services/tools.py`)
Provides a unified interface to run various CLI tools. It handles:
-   Binary path resolution (finding `nuclei`, `nmap` on the system).
-   Command construction based on "Scan Levels" (Basic, Pro, Advanced).
-   Execution via `subprocess`.
-   Standardizing output logging.

**Supported Tools:**
-   **Nuclei**: Template-based vulnerability scanner.
-   **Dalfox**: XSS scanner.
-   **SQLMap**: Automatic SQL injection and database takeover tool.
-   **FFuf**: Fast web fuzzer.
-   **Nmap**: Network mapper.
-   **SSLScan**: TLS/SSL testing.
-   **Httpx**: HTTP probing.

### 4.3 Findings Ingestor (`app/services/findings_ingestor.py`)
Parses the raw JSON/Text output from tools and converts them into standardized `Finding` database records. It handles:
-   Deduplication of findings.
-   Severity mapping (Critical, High, Medium, Low).
-   Enriching findings with metadata.

## 5. Security Features

-   **Multi-Tenancy**: Strict data isolation using `tenant_id` on all major resources.
-   **Authentication**: API Key/Token based authentication.
-   **Internal Security**: `internal_endpoint_security` middleware protects sensitive endpoints.
-   **Input Validation**: Strict Pydantic schemas prevent malformed data.

## 6. How to Run

### Development
1.  Navigate to `backend/`.
2.  Install dependencies: `pip install -r requirements.txt`.
3.  Start services (Redis, DB).
4.  Run API: `uvicorn app.main:app --reload`.
5.  Run Worker: `celery -A app.celery_app worker --loglevel=info`.

### Production
-   Deploy using `Dockerfile`.
-   Run migrations: `alembic upgrade head`.
-   Use `gunicorn` with `uvicorn` workers.
