# RAG Design Document

## Overview

The Thandev Brain Service uses RAG (Retrieval-Augmented Generation) to inform scan planning and report generation. This document describes what gets indexed, how retrieval works, and the "lanes" used for different query types.

## Storage Architecture

### Supported Backends

1. **Qdrant** (Default)
   - Vector database optimized for similarity search
   - Fast, scalable, easy to deploy
   - Recommended for production

2. **PostgreSQL + pgvector**
   - Uses existing PostgreSQL database
   - Good for single-database deployments
   - Requires pgvector extension

### Embedding Providers

1. **Sentence Transformers** (Default)
   - Model: `all-MiniLM-L6-v2` (384 dimensions)
   - Runs locally, no API calls
   - Fast and free

2. **OpenAI**
   - Model: `text-embedding-3-small` (1536 dimensions)
   - Requires API key
   - Higher quality embeddings

## Document Types

### 1. Finding Documents

**Purpose:** Store normalized security findings for retrieval during planning and reporting.

**Fields:**
- `id`: `finding_{finding_id}`
- `title`: Finding title
- `description`: Finding description
- `content`: Combined title + description + CVE + URL
- `doc_type`: `"finding"`
- `org_id`: Organization ID
- `project_id`: Project ID
- `target`: Target URL
- `tool_id`: Tool that found this (nuclei, nmap, etc.)
- `severity`: critical, high, medium, low, info
- `cve_id`: CVE ID if applicable
- `url`: Finding URL
- `created_at`: Timestamp

**Indexed Content:**
- Title + description + CVE ID + URL combined into embedding text

**Retrieval Use Cases:**
- "What vulnerabilities were found on this target before?"
- "Are there any critical findings for this project?"
- "What CVE-related findings exist?"

### 2. Artifact Summary Documents

**Purpose:** Store summaries of tool outputs (NOT huge raw logs).

**Fields:**
- `id`: `artifact_{artifact_id}`
- `title`: `"{tool_id} scan results"`
- `description`: Brief description
- `content`: Summary of artifact (key findings, patterns, NOT full output)
- `doc_type`: `"artifact_summary"`
- `org_id`: Organization ID
- `project_id`: Project ID
- `target`: Target URL
- `tool_id`: Tool that generated this
- `scan_job_id`: Scan job ID
- `finding_count`: Number of findings in artifact
- `created_at`: Timestamp

**Indexed Content:**
- Summary text (e.g., "Found 5 XSS vulnerabilities, 2 SQLi, server: nginx")

**Retrieval Use Cases:**
- "What did previous scans find on this target?"
- "What patterns exist in tool outputs?"

### 3. Technology Fingerprint Documents

**Purpose:** Store detected technology stack information.

**Fields:**
- `id`: `tech_{normalized_target}`
- `title`: `"Technology fingerprint: {target}"`
- `description`: Brief description
- `content`: Server + framework + CMS + languages
- `doc_type`: `"tech_fingerprint"`
- `org_id`: Organization ID
- `project_id`: Project ID
- `target`: Target URL
- `tech_stack`: Full tech stack dict
- `created_at`: Timestamp

**Indexed Content:**
- "Technology fingerprint for {target}\nServer: nginx\nFramework: React\n..."

**Retrieval Use Cases:**
- "What technologies does this target use?"
- "What framework is this app built on?"

### 4. CVE/Template Documents

**Purpose:** Store CVE and template metadata for reference.

**Fields:**
- `id`: `cve_{cve_id}`
- `title`: `"{cve_id}: {template_name}"`
- `description`: Template description
- `content`: CVE ID + name + description + tags
- `doc_type`: `"cve_template"`
- `cve_id`: CVE ID
- `severity`: Template severity
- `tags`: Template tags (xss, sqli, etc.)
- `created_at`: Timestamp

**Indexed Content:**
- "CVE: CVE-2024-XXXX\n{name}\n{description}\nTags: xss, sqli"

**Retrieval Use Cases:**
- "What CVEs are relevant to this target?"
- "What templates match this technology stack?"

## Retrieval Lanes

The RAG system uses "lanes" to organize retrieval by document type and context.

### Lane 1: Latest Findings

**Query:** Recent findings for this project/target

**Filters:**
- `doc_type`: `"finding"`
- `org_id`: Organization ID (optional)
- `project_id`: Project ID (optional)
- `target`: Target URL (optional)

**Use Cases:**
- Planning: "What vulnerabilities were found before?"
- Reporting: "Include similar findings in context"

### Lane 2: Tech Fingerprint

**Query:** Technology stack information

**Filters:**
- `doc_type`: `"tech_fingerprint"`
- `target`: Target URL (optional)

**Use Cases:**
- Planning: "What technologies does this target use?"
- Tool selection: "Use framework-specific tools"

### Lane 3: CVE Templates

**Query:** CVE and template metadata

**Filters:**
- `doc_type`: `"cve_template"`
- `severity`: Severity filter (optional)
- `tags`: Tag filter (optional)

**Use Cases:**
- Planning: "What CVEs are relevant?"
- Tool selection: "Use CVE-specific templates"

### Lane 4: Artifact Summaries

**Query:** Tool artifact summaries

**Filters:**
- `doc_type`: `"artifact_summary"`
- `org_id`: Organization ID (optional)
- `project_id`: Project ID (optional)
- `target`: Target URL (optional)
- `tool_id`: Tool ID (optional)

**Use Cases:**
- Planning: "What did previous scans find?"
- Reporting: "Include artifact context"

## Query Flow

### Planning Query

```
1. Query "latest_findings" lane with target/project filters
   → Get recent findings for this target

2. Query "tech_fingerprint" lane with target filter
   → Get technology stack

3. Query "cve_templates" lane with tech stack context
   → Get relevant CVEs/templates

4. Combine results to inform tool/mode selection
```

### Report Prompt Query

```
1. Query "latest_findings" lane with finding_ids context
   → Get similar findings for evidence

2. Query "artifact_summaries" lane with scan_job_id
   → Get artifact context

3. Query "cve_templates" lane for CVE details
   → Get CVE metadata for findings

4. Pack evidence into prompt package
```

## Indexing Strategy

### When to Index

1. **After Scan Completion:**
   - Index all findings from completed scan
   - Index artifact summaries (tool outputs)
   - Update tech fingerprint if new tech detected

2. **On Finding Creation:**
   - Index new findings immediately (optional, can batch)

3. **On CVE/Template Update:**
   - Index new CVE templates (periodic sync)

### Batch Indexing

- Findings: Batch by scan_job_id
- Artifacts: Index summaries, not raw logs
- Tech fingerprint: Update on first detection or change

## Metadata Fields

All documents include these metadata fields for filtering:

- `org_id`: Organization ID (multi-tenant isolation)
- `project_id`: Project ID (project-specific retrieval)
- `target`: Target URL (target-specific retrieval)
- `doc_type`: Document type (lane filtering)
- `tool_id`: Tool identifier (tool-specific retrieval)
- `severity`: Severity level (finding filtering)
- `created_at`: Timestamp (recency filtering)

## Embedding Strategy

### Text Preparation

1. **Finding Documents:**
   - Combine: `title + description + CVE ID + URL`
   - Example: "XSS vulnerability\nFound in /page endpoint\nCVE: CVE-2024-XXXX\nhttps://target.com/page"

2. **Artifact Summaries:**
   - Use summary text (key findings, patterns)
   - Example: "Found 5 XSS vulnerabilities on /page, 2 SQLi on /api, server: nginx"

3. **Tech Fingerprint:**
   - Combine: `target + server + framework + CMS + languages`
   - Example: "Technology fingerprint for https://target.com\nServer: nginx\nFramework: React\n..."

4. **CVE Templates:**
   - Combine: `CVE ID + name + description + tags`
   - Example: "CVE: CVE-2024-XXXX\nXSS in React\nDescription...\nTags: xss, react"

### Embedding Model Selection

- **Default:** `all-MiniLM-L6-v2` (384 dims, fast, good quality)
- **High Quality:** `text-embedding-3-small` (1536 dims, OpenAI, better for complex queries)

## Performance Considerations

1. **Batch Operations:**
   - Upsert findings in batches (e.g., 100 at a time)
   - Use async/await for non-blocking operations

2. **Indexing:**
   - Create indexes on metadata fields (org_id, project_id, doc_type)
   - Use HNSW index in Qdrant for fast similarity search

3. **Query Optimization:**
   - Limit top_k per lane (default: 5)
   - Use filters to narrow search space
   - Cache frequent queries if needed

## Future Enhancements

1. **Hybrid Search:**
   - Combine vector search with keyword search
   - Use BM25 for exact matches, vectors for semantic

2. **Reranking:**
   - Use cross-encoder for reranking top results
   - Improve relevance of retrieved documents

3. **Temporal Filtering:**
   - Weight recent documents higher
   - Filter by date ranges

4. **Multi-Modal:**
   - Index screenshots, network diagrams
   - Use vision models for image embeddings




