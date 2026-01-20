# Thandev Brain Service - Capabilities Overview

## What is Brain?

The Thandev Brain service is a **RAG (Retrieval-Augmented Generation) powered intelligence service** that provides AI-driven scan planning, report generation, and closed-loop scanning capabilities for the Thandev security platform.

**Key Principle**: The Brain service does NOT execute tools or generate reports directly. It provides planning, prompt building, and orchestration services that the backend uses.

---

## Core Capabilities

### 1. **Intelligent Scan Planning** 🎯

**What it does:**
- Generates intelligent scan plans based on target characteristics, scan level, and technology stack
- Uses RAG (Retrieval-Augmented Generation) to retrieve relevant knowledge from past scans, CVE data, and best practices
- Applies rules-based filtering combined with AI-powered decision making
- Determines optimal tool selection, execution order, dependencies, and timeline estimates

**Input:**
- Target URL
- Scan level (basic, pro, advanced)
- Optional stack information (HTTP headers, server info, detected technologies)
- Organization and project IDs

**Output:**
- Structured scan plan with:
  - List of tool steps (`tool_id`, `mode_id`, `params`, `depends_on`)
  - Timeline estimates per step and total duration
  - Reasoning/explanation for tool selection
  - Parallel execution opportunities

**Endpoint:** `POST /v1/plan-scan`

---

### 2. **Report Prompt Building** 📝

**What it does:**
- Builds comprehensive prompt packages for AI-powered report generation
- Retrieves supporting evidence from RAG store (CVE details, remediation guidance, similar findings)
- Structures findings data with context for OpenAI
- Provides system prompts, user prompts, and JSON schema for structured report generation

**Input:**
- Finding IDs from completed scans
- Scan metadata (target URL, scan level, scan ID)
- Optional artifact references

**Output:**
- Complete prompt package with:
  - System message (role definition for AI)
  - User content (findings data, evidence, artifacts)
  - Report JSON schema (structured output format)
  - Supporting evidence from RAG
  - Instructions for report structure

**Endpoint:** `POST /v1/build-report-prompt`

**Note:** Brain does NOT generate the report JSON itself - it only provides the prompt package. The backend sends this to OpenAI.

---

### 3. **Closed-Loop Scan Orchestration** 🔄

**What it does:**
- Owns the entire scanning process from start to finish
- Dynamically decides next steps based on real-time scan results
- Adapts scan strategy based on findings and diminishing returns
- Manages session state and stop conditions intelligently

**Key Features:**
- **Session Management**: Creates and manages scan sessions with state tracking
- **Adaptive Planning**: Adjusts tool selection and execution order based on intermediate results
- **Stop Conditions**: Automatically stops when:
  - Budget/time limits exceeded
  - Diminishing returns detected (no new findings after N iterations)
  - Vulnerability confirmed present or absent
  - User manually stops
- **Result Ingestion**: Automatically ingests scan findings into RAG for future learning

**Session Lifecycle:**
1. Backend calls `POST /v1/sessions/start` to create session
2. Brain creates session state in Redis
3. Brain controller worker starts closed-loop process:
   - Retrieves RAG evidence for context
   - Decides next steps based on current state
   - Publishes steps to Redis streams
   - Waits for results from Runner service
   - Updates session state
   - Ingests findings summaries to RAG
   - Repeats until stop conditions met
4. Session completes with final status and stop reason

**Endpoints:**
- `POST /v1/sessions/start` - Start new scan session
- `GET /v1/sessions/{session_id}` - Get session status
- `POST /v1/sessions/{session_id}/stop` - Stop session gracefully

---

### 4. **Finding Enrichment** ✨

**What it does:**
- Enriches security findings with AI-generated impact summaries and remediation guidance
- Uses RAG to retrieve similar findings, CVE templates, and technology-specific guidance
- Generates structured remediation steps using OpenAI

**Input:**
- List of findings with basic metadata
- Organization and project IDs
- Target URL for context

**Output:**
- Enriched findings with:
  - Impact summary (what an attacker can do)
  - Remediation summary (high-level fix guidance)
  - Detailed remediation steps (step-by-step instructions)
  - References to CVE data and best practices

**Endpoint:** `POST /v1/enrich-findings`

**Status:** Endpoint exists but may not be fully integrated into all scan pipelines.

---

### 5. **Dependency Scan Explanation** 🔍

**What it does:**
- Generates AI-powered explanations of dependency scanning artifacts
- Fetches scan artifacts from backend (URL-SCA and Repo-SCA results)
- Provides structured explanation with:
  - Summary of detected technologies and vulnerabilities
  - Key points about findings
  - Prioritized actions (most critical first)
  - Limitations and confidence notes

**Input:**
- Scan ID
- Optional organization and project IDs

**Output:**
- Structured explanation:
  - Summary text
  - Key points (list)
  - Prioritized actions (list with titles, reasons, references)
  - Limitations (list of caveats)

**Endpoint:** `POST /v1/scans/{scan_id}/explain`

**Note:** Strictly grounded in artifacts - no hallucinations. Only references what is actually in scan data.

---

### 6. **Tool Catalog Management** 📚

**What it does:**
- Provides access to the complete tool catalog with all available security tools and execution modes
- Returns tool metadata, capabilities, requirements, and parameter schemas

**Output:**
- Complete catalog with:
  - Tools list (nuclei, nmap, httpx, ffuf, dalfox, sqlmap, etc.)
  - Modes per tool (e.g., `nuclei-fast`, `nuclei-deep`, `nmap-top-ports`)
  - Parameter schemas for each mode
  - Constraints (timeouts, resource limits)
  - Target type compatibility

**Endpoint:** `GET /v1/catalog`

**Usage:** Used by backend for validation and frontend for UI display.

---

### 7. **RAG Knowledge Base** 🧠

**What it does:**
- Maintains a vector database of security knowledge
- Stores and retrieves relevant information for scan planning and report generation
- Supports multiple vector store backends (Qdrant, PgVector)
- Supports multiple embedding providers (OpenAI, sentence-transformers)

**What's Stored:**
- CVE descriptions and references (from NVD)
- Security tool documentation
- Past scan results (if indexed)
- Security best practices and remediation guides
- Vulnerability patterns and signatures

**RAG Endpoints:**
- RAG management endpoints under `/v1/rag/` prefix
- Indexing and retrieval operations

**Benefits:**
- Context-aware planning based on historical data
- Evidence-based report generation
- Learning from past scans to improve future planning

---

## Technical Capabilities

### **LLM Integration**
- **OpenAI Integration**: Uses GPT-4/GPT-3.5-turbo for planning and report generation
- **Embedding Models**: Supports OpenAI embeddings or local sentence-transformers
- **Temperature Control**: Configurable per endpoint (0.3 for reports, 0.7 for planning)
- **Token Limits**: Configurable max tokens per request

### **Vector Store Support**
- **Qdrant**: Default vector database (recommended)
- **PgVector**: PostgreSQL vector extension (alternative)
- **Collection Management**: Configurable collection names and indexing strategies

### **Error Handling & Resilience**
- **Input Validation**: Pydantic models validate all requests
- **Timeout Protection**: HTTP client timeouts prevent hanging requests
- **Graceful Degradation**: Backend can fall back to rule-based planning if Brain unavailable
- **Error Logging**: Comprehensive error logging with stack traces

### **Performance & Limits**
- **Max Steps**: Configurable maximum steps per plan (default: 20)
- **Max Parallelism**: Configurable parallel execution (default: 5)
- **Max Runtime**: Configurable total scan runtime limits (default: 3600s)
- **RAG Result Limits**: Top K results for vector search

---

## Integration Points

### **With Backend Service**
- Backend calls Brain via HTTP client (`brain_client.py`)
- Fallback behavior when Brain unavailable (if `BRAIN_REQUIRED=false`)
- Session coordination between backend and Brain

### **With Runner Service**
- Brain publishes step requests to Redis streams
- Runner consumes steps and executes tools
- Runner publishes results back to Brain via Redis streams
- Brain consumes results and decides next steps

### **With Frontend**
- Frontend can query catalog for tool information
- Frontend displays session status from Brain
- Frontend shows AI-generated explanations

---

## Configuration

### **Required Environment Variables**
- `OPENAI_API_KEY`: OpenAI API key (required for LLM features)
- `RAG_STORE_TYPE`: `qdrant` or `pgvector`
- `QDRANT_URL`: Qdrant server URL (if using Qdrant)
- `EMBEDDING_PROVIDER`: `openai` or `sentence_transformers`

### **Optional Configuration**
- `BRAIN_MAX_STEPS`: Maximum steps in a plan
- `BRAIN_MAX_PARALLELISM`: Maximum parallel steps
- `BRAIN_MAX_TOTAL_RUNTIME_SEC`: Maximum total scan runtime
- `OPENAI_MODEL`: Model to use (default: `gpt-4` or `gpt-3.5-turbo`)
- `OPENAI_EMBEDDING_MODEL`: Embedding model (default: `text-embedding-3-small`)

---

## What Brain Does NOT Do

1. **Does NOT execute security tools** - Only plans and orchestrates
2. **Does NOT generate report JSON directly** - Only provides prompt packages
3. **Does NOT store scan results** - Backend owns all data persistence
4. **Does NOT modify backend database** - All data changes go through backend API
5. **Does NOT output shell commands** - Only returns structured tool/mode/params

---

## Summary

The Thandev Brain service is a **powerful AI orchestration layer** that:

✅ **Plans** intelligent scans using RAG + rules  
✅ **Orchestrates** closed-loop scanning with adaptive decision-making  
✅ **Enriches** findings with AI-generated context and remediation  
✅ **Explains** dependency scan results in human-readable format  
✅ **Builds** comprehensive prompts for AI report generation  
✅ **Learns** from past scans to improve future planning  

It transforms Thandev from a static tool executor into an **intelligent, adaptive security scanning platform** that gets smarter over time.
