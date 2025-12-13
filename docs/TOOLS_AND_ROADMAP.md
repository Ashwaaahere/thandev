# Thandev Tools Status & Roadmap

**Last Updated**: January 2025  
**Purpose**: Track active tools, stubbed features, and future work items

---

## Tool Selection Configuration

**Important**: Tool selection for each scan level is controlled by the **Tool Matrix** in `backend/app/core/tool_matrix.py`. This is the **single source of truth** for which tools run at each scan level.

- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap  
- **Advanced**: Nuclei + Nmap + SSLScan

To modify which tools run at each level, edit `TOOL_MATRIX` in `app/core/tool_matrix.py`. The orchestration code automatically uses this configuration.

**Adding a new tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels
3. Extend the orchestration routing logic if needed (most tools work automatically)
4. Add parsing logic in `app/services/findings_ingestor.py`

---

## Table of Contents
1. [Active Tools](#active-tools)
2. [Stubbed/Placeholder Features](#stubbedplaceholder-features)
3. [Future Work & TODOs](#future-work--todos)
4. [Maintenance Guide](#maintenance-guide)

---

## Active Tools

### ✅ Security Scanning Tools

#### **1. Nuclei (Vulnerability Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nuclei()`
- **Version**: Nuclei v3.4.10
- **Implementation**:
  - Executes via subprocess
  - Supports severity filtering (low, medium, high, critical, info)
  - Uses template tags (cve, vulnerability, exposure, misconfig, etc.)
  - Output format: JSONL (JSON Lines)
  - Rate limiting: 50 requests/second
  - Timeout: 30 minutes per scan
  - Retries: 1 retry on failure
- **Scan Level Configuration**:
  - **Basic**: `low,medium` severity, `cve,vulnerability,exposure` tags
  - **Pro**: `low,medium,high` severity, `cve,vulnerability,exposure,misconfig,default-login` tags
  - **Advanced**: `low,medium,high,critical,info` severity, `cve,vulnerability,exposure,misconfig,default-login,tech,ssl` tags
- **Error Handling**: 
  - Checks if nuclei binary exists before execution
  - Handles timeouts gracefully
  - Distinguishes between "no findings" (success) and actual errors
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nuclei_output()`

#### **2. Nmap (Port Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nmap()`
- **Implementation**:
  - Executes via subprocess
  - Output format: XML (`-oX -`)
  - Timeout: 30 minutes
- **Scan Level Configuration**:
  - **Basic**: `--top-ports 100 -sV` (top 100 ports, version detection)
  - **Pro**: `-sV -sC --top-ports 1000` (version detection, default scripts, top 1000 ports)
  - **Advanced**: `-sV -sC -A -p-` (version detection, default scripts, aggressive, all ports)
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nmap_output()`

#### **3. SSLScan (TLS/SSL Analyzer)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_sslscan()`
- **Implementation**:
  - Executes via subprocess
  - Output format: JSON (`--json`)
  - Timeout: 5 minutes
  - Fallback: Uses `openssl s_client` if sslscan not available
- **Fallback Implementation**: `_run_openssl_fallback()` uses OpenSSL for basic SSL checks
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_sslscan_output()`

### ✅ Performance Scanning Tools

#### **4. Lighthouse (Performance Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/performance_scanner.py`
- **Implementation**:
  - Supports both local and Cloud Run execution
  - Local: Uses subprocess to run `lighthouse` CLI
  - Cloud Run: Calls external Cloud Run service (if configured)
  - Device modes: `desktop` (default), `mobile` (future)
- **Metrics Extracted**:
  - Performance score (0-100)
  - First Contentful Paint (FCP)
  - Largest Contentful Paint (LCP)
  - Time to Interactive (TTI)
  - Cumulative Layout Shift (CLS)
  - First Input Delay (FID)
  - Speed Index
  - Total requests and page size
- **Output Format**: JSON with categories, metrics, opportunities, diagnostics
- **Timeout**: 5 minutes (300 seconds)

### ✅ Supporting Services

#### **5. Scan Orchestrator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/scan_orchestrator.py`
- **Features**:
  - Queues scans via Celery
  - Manages scan execution pipeline
  - Coordinates tool execution
  - Generates AI reports
  - Updates scan status

#### **6. Findings Ingestor**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/findings_ingestor.py`
- **Features**:
  - Parses Nuclei JSONL output
  - Parses Nmap XML output
  - Parses SSLScan JSON/text output
  - Creates Finding records in database
  - Extracts CVE/CWE IDs, CVSS scores, severity

#### **7. AI Reporter**
- **Status**: ⚠️ **PARTIALLY ACTIVE** (Rule-based, LLM TODO)
- **Location**: `backend/app/services/ai/reporter.py`
- **Current Implementation**:
  - Rule-based report generation
  - Generates executive summary
  - Identifies top risks
  - Calculates risk score
  - Creates remediation overview
- **Limitation**: Uses rule-based logic, not LLM (see TODOs)

#### **8. PDF Report Generator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/pdf_reports.py`
- **Features**:
  - Generates branded PDF reports using ReportLab
  - Two modes: `full` (detailed) and `executive` (summary)
  - Sections: Cover, Executive Summary, Network/TLS, Stack Fingerprint, Findings Detail
  - Multi-tenant scoped

---

## Stubbed/Placeholder Features

### ⚠️ Deprecated/Unused Functions

#### **1. `run_nuclei_basic()`**
- **Status**: ❌ **STUB - NOT USED**
- **Location**: `backend/app/services/tools.py:16`
- **Reason**: Replaced by `ToolExecutor._run_nuclei()` which is the active implementation
- **Action**: Can be removed in future cleanup

#### **2. `run_basic_scan_for_job()`**
- **Status**: ❌ **DEPRECATED**
- **Location**: `backend/app/services/scan_orchestrator.py:70`
- **Reason**: Replaced by `run_scan_for_job()` which handles all scan levels
- **Action**: Marked as deprecated, can be removed

### ⚠️ Placeholder Services

#### **3. AI Adaptive Scanner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/adaptive.py`
- **Current State**: 
  - Function `refine_scan()` exists but returns placeholder logic
  - Intended for future adaptive scanning based on stack info
- **Future**: Will analyze stack info and adjust scan strategy dynamically

#### **4. AI Planner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/planner.py`
- **Current State**:
  - Function `plan_scan()` exists but returns basic plan
  - Intended for future intelligent scan planning
- **Future**: Will create custom scan plans based on target characteristics

---

## Future Work & TODOs

### 🔴 High Priority

#### **1. LLM Integration for AI Reports**
- **Status**: ❌ **TODO**
- **Location**: `backend/app/services/ai/reporter.py:89`
- **Current**: Rule-based report generation
- **Needed**:
  - Integrate OpenAI or Anthropic API
  - Generate richer executive summaries
  - Create contextual remediation recommendations
  - Analyze findings for patterns and trends
- **Estimated Effort**: 2-3 days
- **Dependencies**: API keys, LLM service account

#### **2. Enhanced Authentication**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/core/tenant_utils.py`
- **Current**: 
  - Uses header-based authentication (`X-Thandev-User-Id`, `X-Thandev-Tenant-Id`)
  - No JWT validation (structure ready for future)
- **Needed**:
  - JWT token validation
  - Session sync between NextAuth and backend
  - Support for multiple users per tenant (org accounts)
- **Estimated Effort**: 3-5 days

#### **3. Database Migrations**
- **Status**: ❌ **TODO**
- **Location**: Development uses `Base.metadata.create_all()`
- **Current**: Manual schema changes in development
- **Needed**:
  - Set up Alembic migrations
  - Create migration scripts for production
  - Version control for schema changes
- **Estimated Effort**: 1-2 days

### 🟡 Medium Priority

#### **4. Rate Limiting**
- **Status**: ⚠️ **PARTIAL**
- **Location**: Only legacy security router has rate limiting
- **Current**: Plan-based limits (monthly scans, concurrent scans)
- **Needed**:
  - API-level rate limiting (per endpoint)
  - Per-user rate limiting
  - DDoS protection
- **Estimated Effort**: 2-3 days

#### **5. Monitoring & Logging**
- **Status**: ❌ **TODO**
- **Current**: Basic Python logging
- **Needed**:
  - Structured logging (JSON format)
  - Metrics collection (Prometheus)
  - Error tracking (Sentry)
  - Performance monitoring
- **Estimated Effort**: 3-4 days

#### **6. Caching Strategy**
- **Status**: ⚠️ **MINIMAL**
- **Location**: `backend/app/utils/cache.py` exists but minimal usage
- **Current**: Redis configured but underutilized
- **Needed**:
  - Cache RSS feed results (news page)
  - Cache project stats
  - Cache scan results (with TTL)
  - Cache user sessions
- **Estimated Effort**: 2-3 days

#### **7. Performance Scan Enhancements**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/api/performance.py:106`
- **Current**: 
  - Lighthouse integration works
  - Device selection hardcoded to "desktop"
- **Needed**:
  - Device selection based on scan level or user preference
  - Mobile device emulation
  - Network throttling simulation
  - Performance recommendations
- **Estimated Effort**: 2-3 days

### 🟢 Low Priority / Future Enhancements

#### **8. Additional Security Tools**
- **Status**: ❌ **FUTURE**
- **Potential Tools**:
  - **Subfinder/Amass**: Subdomain enumeration
  - **FFuf/Gobuster**: Directory/file discovery
  - **Nikto**: HTTP server vulnerability scanner
  - **SQLMap**: SQL injection testing (with authorization)
- **Estimated Effort**: 5-7 days per tool

#### **9. Cloud Run Integration**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/services/performance_scanner.py:142`
- **Current**: 
  - Performance scans support Cloud Run
  - Security scans use local execution
- **Needed**:
  - Migrate security scans to Cloud Run for scalability
  - Support for distributed scanning
  - Job queue management
- **Estimated Effort**: 5-7 days

#### **10. Advanced AI Features**
- **Status**: ❌ **FUTURE**
- **Features**:
  - Adaptive scanning based on stack info
  - Intelligent scan planning
  - Finding correlation and deduplication
  - Risk prediction
- **Estimated Effort**: 10-15 days

#### **11. Data Enrichment**
- **Status**: ❌ **FUTURE**
- **Location**: `backend/THANDEV_V2_STRUCTURE.md` mentions `ingest_nvd`, `ingest_kev`
- **Needed**:
  - NVD (National Vulnerability Database) integration
  - KEV (Known Exploited Vulnerabilities) integration
  - CVE/CWE metadata enrichment
  - Exploit availability checking
- **Estimated Effort**: 7-10 days

#### **12. Frontend Enhancements**
- **Status**: ⚠️ **ONGOING**
- **Current Gaps**:
  - Toast notifications (currently using alerts)
  - Better loading states (some pages lack skeletons)
  - Empty state handling (some pages need improvement)
  - Error boundaries
- **Estimated Effort**: 3-5 days

---

## Tool Execution Flow

### Current Active Flow

```
1. User creates scan via API
   ↓
2. ScanJob created (status: PENDING)
   ↓
3. Celery task queued (status: QUEUED)
   ↓
4. Celery worker picks up task (status: RUNNING)
   ↓
5. ScanOrchestrator.run_scan_for_job()
   ↓
6. Get scan profile for level (basic/pro/advanced)
   ↓
7. For each tool in profile:
   ├─ ToolExecutor.run_tool()
   ├─ Execute tool via subprocess
   ├─ Save output to data/jobs/{job_id}/{tool}_output.json
   ├─ FindingsIngestor.parse_{tool}_output()
   └─ Create Finding records
   ↓
8. AI Reporter.generate_basic_report()
   ↓
9. Update ScanJob (status: COMPLETED, summary: {...})
```

### Tool Configuration

**Tool Matrix** (`backend/app/core/tool_matrix.py`):
- **Single source of truth** for tool selection per scan level
- Uses `ScanLevel` enum (BASIC, PRO, ADVANCED)
- Defines `TOOL_MATRIX` mapping scan levels to `ToolConfig` lists
- Helper functions: `get_tools_for_level()`, `get_enabled_tool_keys()`, `is_tool_enabled_for_level()`
- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap
- **Advanced**: Nuclei + Nmap + SSLScan

**Scan Profiles** (`backend/app/services/scan_profiles.py`):
- Provides backward-compatible interface
- Now uses `tool_matrix` as the source of truth
- Converts `ToolConfig` to legacy profile format for compatibility

**Tool Executor** (`backend/app/services/tools.py`):
- Supports: `nuclei`, `nmap`, `sslscan`
- Each tool has async `_run_{tool}()` method
- Returns structured result with output, exit_code, command

**Adding a New Tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels in `app/core/tool_matrix.py`
3. Extend the orchestration routing logic in `scan_orchestrator.py` if needed
4. Update this documentation

---

## Maintenance Guide

### How to Keep This Document Updated

#### **When Adding a New Tool**:
1. **Implement the tool runner** in `app/services/tools.py`:
   - Add tool method to `ToolExecutor` (e.g., `_run_newtool()`)
   - Add tool key to `ToolExecutor.supported_tools` dict
   
2. **Add tool to tool matrix** in `app/core/tool_matrix.py`:
   - Add `{"key": "newtool", "enabled": True}` to `TOOL_MATRIX` for desired scan levels
   - This is the **single source of truth** for tool selection
   
3. **Update orchestration** in `app/services/scan_orchestrator.py` if needed:
   - Most tools work automatically via `ToolExecutor.run_tool()`
   - Only add custom routing if tool needs special handling
   
4. **Add parsing logic** in `app/services/findings_ingestor.py`:
   - Create `parse_newtool_output()` function
   - Create `ingest_newtool_findings()` function
   - Follow the same pattern as existing tools
   
5. **Update documentation**:
   - Add tool to "Active Tools" section in this file
   - Document implementation location, configuration, output format
   - Update "Tool Configuration" section

#### **When Marking a Feature as Complete**:
1. Move from "Future Work" to "Active Tools"
2. Update status from ❌ TODO to ✅ ACTIVE
3. Add completion date
4. Document any limitations or known issues

#### **When Deprecating a Feature**:
1. Move to "Stubbed/Placeholder Features"
2. Mark as ❌ DEPRECATED or ⚠️ STUB
3. Document reason for deprecation
4. Note replacement (if any)

#### **When Adding a TODO**:
1. Add to appropriate priority section (High/Medium/Low)
2. Include:
   - Current status
   - Location (file path)
   - What's needed
   - Estimated effort
   - Dependencies
3. Update "Last Updated" date at top

#### **Regular Review Schedule**:
- **Weekly**: Review TODOs and update priorities
- **Monthly**: Review completed work and move to "Active Tools"
- **Quarterly**: Review roadmap and adjust estimates

### Status Indicators

- ✅ **FULLY ACTIVE**: Feature is complete and working in production
- ⚠️ **PARTIALLY ACTIVE**: Feature works but has limitations or TODOs
- ❌ **TODO**: Feature not yet implemented
- 🚧 **IN PROGRESS**: Feature currently being developed
- 🔴 **HIGH PRIORITY**: Should be addressed soon
- 🟡 **MEDIUM PRIORITY**: Important but not urgent
- 🟢 **LOW PRIORITY**: Nice to have, future enhancement

---

## Quick Reference

### Active Tool Commands

**Nuclei**:
```bash
nuclei -u <target_url> -severity <levels> -tags <tags> -jsonl -silent -rate-limit 50 -timeout 10 -retries 1
```

**Nmap**:
```bash
nmap -oX - <scan_args> <hostname>
```

**SSLScan**:
```bash
sslscan --json <hostname>:<port>
```

**Lighthouse** (Local):
```bash
lighthouse <url> --output=json --output-path=<path> --only-categories=performance --preset=desktop
```

### File Locations

- **Tool Execution**: `backend/app/services/tools.py`
- **Scan Orchestration**: `backend/app/services/scan_orchestrator.py`
- **Findings Parsing**: `backend/app/services/findings_ingestor.py`
- **AI Reporting**: `backend/app/services/ai/reporter.py`
- **Scan Profiles**: `backend/app/services/scan_profiles.py`
- **Performance Scanner**: `backend/app/services/performance_scanner.py`
- **PDF Reports**: `backend/app/services/pdf_reports.py`

---

## Summary

### Current State (January 2025)

**Active Tools**: 4 (Nuclei, Nmap, SSLScan, Lighthouse)  
**Supporting Services**: 4 (Orchestrator, Ingestor, Reporter, PDF Generator)  
**Stubbed Features**: 2 (run_nuclei_basic, run_basic_scan_for_job)  
**Placeholder Services**: 2 (AI Adaptive, AI Planner)  
**High Priority TODOs**: 3  
**Medium Priority TODOs**: 4  
**Low Priority TODOs**: 5  

### Next Steps

1. **Immediate**: Complete LLM integration for AI reports
2. **Short-term**: Set up Alembic migrations
3. **Short-term**: Enhance authentication with JWT
4. **Medium-term**: Add monitoring and structured logging
5. **Long-term**: Expand tool suite and Cloud Run integration

---

*This document should be updated whenever tools are added, modified, or deprecated.*  
*Last review date should be updated in the header.*


**Last Updated**: January 2025  
**Purpose**: Track active tools, stubbed features, and future work items

---

## Tool Selection Configuration

**Important**: Tool selection for each scan level is controlled by the **Tool Matrix** in `backend/app/core/tool_matrix.py`. This is the **single source of truth** for which tools run at each scan level.

- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap  
- **Advanced**: Nuclei + Nmap + SSLScan

To modify which tools run at each level, edit `TOOL_MATRIX` in `app/core/tool_matrix.py`. The orchestration code automatically uses this configuration.

**Adding a new tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels
3. Extend the orchestration routing logic if needed (most tools work automatically)
4. Add parsing logic in `app/services/findings_ingestor.py`

---

## Table of Contents
1. [Active Tools](#active-tools)
2. [Stubbed/Placeholder Features](#stubbedplaceholder-features)
3. [Future Work & TODOs](#future-work--todos)
4. [Maintenance Guide](#maintenance-guide)

---

## Active Tools

### ✅ Security Scanning Tools

#### **1. Nuclei (Vulnerability Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nuclei()`
- **Version**: Nuclei v3.4.10
- **Implementation**:
  - Executes via subprocess
  - Supports severity filtering (low, medium, high, critical, info)
  - Uses template tags (cve, vulnerability, exposure, misconfig, etc.)
  - Output format: JSONL (JSON Lines)
  - Rate limiting: 50 requests/second
  - Timeout: 30 minutes per scan
  - Retries: 1 retry on failure
- **Scan Level Configuration**:
  - **Basic**: `low,medium` severity, `cve,vulnerability,exposure` tags
  - **Pro**: `low,medium,high` severity, `cve,vulnerability,exposure,misconfig,default-login` tags
  - **Advanced**: `low,medium,high,critical,info` severity, `cve,vulnerability,exposure,misconfig,default-login,tech,ssl` tags
- **Error Handling**: 
  - Checks if nuclei binary exists before execution
  - Handles timeouts gracefully
  - Distinguishes between "no findings" (success) and actual errors
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nuclei_output()`

#### **2. Nmap (Port Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nmap()`
- **Implementation**:
  - Executes via subprocess
  - Output format: XML (`-oX -`)
  - Timeout: 30 minutes
- **Scan Level Configuration**:
  - **Basic**: `--top-ports 100 -sV` (top 100 ports, version detection)
  - **Pro**: `-sV -sC --top-ports 1000` (version detection, default scripts, top 1000 ports)
  - **Advanced**: `-sV -sC -A -p-` (version detection, default scripts, aggressive, all ports)
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nmap_output()`

#### **3. SSLScan (TLS/SSL Analyzer)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_sslscan()`
- **Implementation**:
  - Executes via subprocess
  - Output format: JSON (`--json`)
  - Timeout: 5 minutes
  - Fallback: Uses `openssl s_client` if sslscan not available
- **Fallback Implementation**: `_run_openssl_fallback()` uses OpenSSL for basic SSL checks
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_sslscan_output()`

### ✅ Performance Scanning Tools

#### **4. Lighthouse (Performance Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/performance_scanner.py`
- **Implementation**:
  - Supports both local and Cloud Run execution
  - Local: Uses subprocess to run `lighthouse` CLI
  - Cloud Run: Calls external Cloud Run service (if configured)
  - Device modes: `desktop` (default), `mobile` (future)
- **Metrics Extracted**:
  - Performance score (0-100)
  - First Contentful Paint (FCP)
  - Largest Contentful Paint (LCP)
  - Time to Interactive (TTI)
  - Cumulative Layout Shift (CLS)
  - First Input Delay (FID)
  - Speed Index
  - Total requests and page size
- **Output Format**: JSON with categories, metrics, opportunities, diagnostics
- **Timeout**: 5 minutes (300 seconds)

### ✅ Supporting Services

#### **5. Scan Orchestrator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/scan_orchestrator.py`
- **Features**:
  - Queues scans via Celery
  - Manages scan execution pipeline
  - Coordinates tool execution
  - Generates AI reports
  - Updates scan status

#### **6. Findings Ingestor**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/findings_ingestor.py`
- **Features**:
  - Parses Nuclei JSONL output
  - Parses Nmap XML output
  - Parses SSLScan JSON/text output
  - Creates Finding records in database
  - Extracts CVE/CWE IDs, CVSS scores, severity

#### **7. AI Reporter**
- **Status**: ⚠️ **PARTIALLY ACTIVE** (Rule-based, LLM TODO)
- **Location**: `backend/app/services/ai/reporter.py`
- **Current Implementation**:
  - Rule-based report generation
  - Generates executive summary
  - Identifies top risks
  - Calculates risk score
  - Creates remediation overview
- **Limitation**: Uses rule-based logic, not LLM (see TODOs)

#### **8. PDF Report Generator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/pdf_reports.py`
- **Features**:
  - Generates branded PDF reports using ReportLab
  - Two modes: `full` (detailed) and `executive` (summary)
  - Sections: Cover, Executive Summary, Network/TLS, Stack Fingerprint, Findings Detail
  - Multi-tenant scoped

---

## Stubbed/Placeholder Features

### ⚠️ Deprecated/Unused Functions

#### **1. `run_nuclei_basic()`**
- **Status**: ❌ **STUB - NOT USED**
- **Location**: `backend/app/services/tools.py:16`
- **Reason**: Replaced by `ToolExecutor._run_nuclei()` which is the active implementation
- **Action**: Can be removed in future cleanup

#### **2. `run_basic_scan_for_job()`**
- **Status**: ❌ **DEPRECATED**
- **Location**: `backend/app/services/scan_orchestrator.py:70`
- **Reason**: Replaced by `run_scan_for_job()` which handles all scan levels
- **Action**: Marked as deprecated, can be removed

### ⚠️ Placeholder Services

#### **3. AI Adaptive Scanner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/adaptive.py`
- **Current State**: 
  - Function `refine_scan()` exists but returns placeholder logic
  - Intended for future adaptive scanning based on stack info
- **Future**: Will analyze stack info and adjust scan strategy dynamically

#### **4. AI Planner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/planner.py`
- **Current State**:
  - Function `plan_scan()` exists but returns basic plan
  - Intended for future intelligent scan planning
- **Future**: Will create custom scan plans based on target characteristics

---

## Future Work & TODOs

### 🔴 High Priority

#### **1. LLM Integration for AI Reports**
- **Status**: ❌ **TODO**
- **Location**: `backend/app/services/ai/reporter.py:89`
- **Current**: Rule-based report generation
- **Needed**:
  - Integrate OpenAI or Anthropic API
  - Generate richer executive summaries
  - Create contextual remediation recommendations
  - Analyze findings for patterns and trends
- **Estimated Effort**: 2-3 days
- **Dependencies**: API keys, LLM service account

#### **2. Enhanced Authentication**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/core/tenant_utils.py`
- **Current**: 
  - Uses header-based authentication (`X-Thandev-User-Id`, `X-Thandev-Tenant-Id`)
  - No JWT validation (structure ready for future)
- **Needed**:
  - JWT token validation
  - Session sync between NextAuth and backend
  - Support for multiple users per tenant (org accounts)
- **Estimated Effort**: 3-5 days

#### **3. Database Migrations**
- **Status**: ❌ **TODO**
- **Location**: Development uses `Base.metadata.create_all()`
- **Current**: Manual schema changes in development
- **Needed**:
  - Set up Alembic migrations
  - Create migration scripts for production
  - Version control for schema changes
- **Estimated Effort**: 1-2 days

### 🟡 Medium Priority

#### **4. Rate Limiting**
- **Status**: ⚠️ **PARTIAL**
- **Location**: Only legacy security router has rate limiting
- **Current**: Plan-based limits (monthly scans, concurrent scans)
- **Needed**:
  - API-level rate limiting (per endpoint)
  - Per-user rate limiting
  - DDoS protection
- **Estimated Effort**: 2-3 days

#### **5. Monitoring & Logging**
- **Status**: ❌ **TODO**
- **Current**: Basic Python logging
- **Needed**:
  - Structured logging (JSON format)
  - Metrics collection (Prometheus)
  - Error tracking (Sentry)
  - Performance monitoring
- **Estimated Effort**: 3-4 days

#### **6. Caching Strategy**
- **Status**: ⚠️ **MINIMAL**
- **Location**: `backend/app/utils/cache.py` exists but minimal usage
- **Current**: Redis configured but underutilized
- **Needed**:
  - Cache RSS feed results (news page)
  - Cache project stats
  - Cache scan results (with TTL)
  - Cache user sessions
- **Estimated Effort**: 2-3 days

#### **7. Performance Scan Enhancements**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/api/performance.py:106`
- **Current**: 
  - Lighthouse integration works
  - Device selection hardcoded to "desktop"
- **Needed**:
  - Device selection based on scan level or user preference
  - Mobile device emulation
  - Network throttling simulation
  - Performance recommendations
- **Estimated Effort**: 2-3 days

### 🟢 Low Priority / Future Enhancements

#### **8. Additional Security Tools**
- **Status**: ❌ **FUTURE**
- **Potential Tools**:
  - **Subfinder/Amass**: Subdomain enumeration
  - **FFuf/Gobuster**: Directory/file discovery
  - **Nikto**: HTTP server vulnerability scanner
  - **SQLMap**: SQL injection testing (with authorization)
- **Estimated Effort**: 5-7 days per tool

#### **9. Cloud Run Integration**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/services/performance_scanner.py:142`
- **Current**: 
  - Performance scans support Cloud Run
  - Security scans use local execution
- **Needed**:
  - Migrate security scans to Cloud Run for scalability
  - Support for distributed scanning
  - Job queue management
- **Estimated Effort**: 5-7 days

#### **10. Advanced AI Features**
- **Status**: ❌ **FUTURE**
- **Features**:
  - Adaptive scanning based on stack info
  - Intelligent scan planning
  - Finding correlation and deduplication
  - Risk prediction
- **Estimated Effort**: 10-15 days

#### **11. Data Enrichment**
- **Status**: ❌ **FUTURE**
- **Location**: `backend/THANDEV_V2_STRUCTURE.md` mentions `ingest_nvd`, `ingest_kev`
- **Needed**:
  - NVD (National Vulnerability Database) integration
  - KEV (Known Exploited Vulnerabilities) integration
  - CVE/CWE metadata enrichment
  - Exploit availability checking
- **Estimated Effort**: 7-10 days

#### **12. Frontend Enhancements**
- **Status**: ⚠️ **ONGOING**
- **Current Gaps**:
  - Toast notifications (currently using alerts)
  - Better loading states (some pages lack skeletons)
  - Empty state handling (some pages need improvement)
  - Error boundaries
- **Estimated Effort**: 3-5 days

---

## Tool Execution Flow

### Current Active Flow

```
1. User creates scan via API
   ↓
2. ScanJob created (status: PENDING)
   ↓
3. Celery task queued (status: QUEUED)
   ↓
4. Celery worker picks up task (status: RUNNING)
   ↓
5. ScanOrchestrator.run_scan_for_job()
   ↓
6. Get scan profile for level (basic/pro/advanced)
   ↓
7. For each tool in profile:
   ├─ ToolExecutor.run_tool()
   ├─ Execute tool via subprocess
   ├─ Save output to data/jobs/{job_id}/{tool}_output.json
   ├─ FindingsIngestor.parse_{tool}_output()
   └─ Create Finding records
   ↓
8. AI Reporter.generate_basic_report()
   ↓
9. Update ScanJob (status: COMPLETED, summary: {...})
```

### Tool Configuration

**Tool Matrix** (`backend/app/core/tool_matrix.py`):
- **Single source of truth** for tool selection per scan level
- Uses `ScanLevel` enum (BASIC, PRO, ADVANCED)
- Defines `TOOL_MATRIX` mapping scan levels to `ToolConfig` lists
- Helper functions: `get_tools_for_level()`, `get_enabled_tool_keys()`, `is_tool_enabled_for_level()`
- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap
- **Advanced**: Nuclei + Nmap + SSLScan

**Scan Profiles** (`backend/app/services/scan_profiles.py`):
- Provides backward-compatible interface
- Now uses `tool_matrix` as the source of truth
- Converts `ToolConfig` to legacy profile format for compatibility

**Tool Executor** (`backend/app/services/tools.py`):
- Supports: `nuclei`, `nmap`, `sslscan`
- Each tool has async `_run_{tool}()` method
- Returns structured result with output, exit_code, command

**Adding a New Tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels in `app/core/tool_matrix.py`
3. Extend the orchestration routing logic in `scan_orchestrator.py` if needed
4. Update this documentation

---

## Maintenance Guide

### How to Keep This Document Updated

#### **When Adding a New Tool**:
1. **Implement the tool runner** in `app/services/tools.py`:
   - Add tool method to `ToolExecutor` (e.g., `_run_newtool()`)
   - Add tool key to `ToolExecutor.supported_tools` dict
   
2. **Add tool to tool matrix** in `app/core/tool_matrix.py`:
   - Add `{"key": "newtool", "enabled": True}` to `TOOL_MATRIX` for desired scan levels
   - This is the **single source of truth** for tool selection
   
3. **Update orchestration** in `app/services/scan_orchestrator.py` if needed:
   - Most tools work automatically via `ToolExecutor.run_tool()`
   - Only add custom routing if tool needs special handling
   
4. **Add parsing logic** in `app/services/findings_ingestor.py`:
   - Create `parse_newtool_output()` function
   - Create `ingest_newtool_findings()` function
   - Follow the same pattern as existing tools
   
5. **Update documentation**:
   - Add tool to "Active Tools" section in this file
   - Document implementation location, configuration, output format
   - Update "Tool Configuration" section

#### **When Marking a Feature as Complete**:
1. Move from "Future Work" to "Active Tools"
2. Update status from ❌ TODO to ✅ ACTIVE
3. Add completion date
4. Document any limitations or known issues

#### **When Deprecating a Feature**:
1. Move to "Stubbed/Placeholder Features"
2. Mark as ❌ DEPRECATED or ⚠️ STUB
3. Document reason for deprecation
4. Note replacement (if any)

#### **When Adding a TODO**:
1. Add to appropriate priority section (High/Medium/Low)
2. Include:
   - Current status
   - Location (file path)
   - What's needed
   - Estimated effort
   - Dependencies
3. Update "Last Updated" date at top

#### **Regular Review Schedule**:
- **Weekly**: Review TODOs and update priorities
- **Monthly**: Review completed work and move to "Active Tools"
- **Quarterly**: Review roadmap and adjust estimates

### Status Indicators

- ✅ **FULLY ACTIVE**: Feature is complete and working in production
- ⚠️ **PARTIALLY ACTIVE**: Feature works but has limitations or TODOs
- ❌ **TODO**: Feature not yet implemented
- 🚧 **IN PROGRESS**: Feature currently being developed
- 🔴 **HIGH PRIORITY**: Should be addressed soon
- 🟡 **MEDIUM PRIORITY**: Important but not urgent
- 🟢 **LOW PRIORITY**: Nice to have, future enhancement

---

## Quick Reference

### Active Tool Commands

**Nuclei**:
```bash
nuclei -u <target_url> -severity <levels> -tags <tags> -jsonl -silent -rate-limit 50 -timeout 10 -retries 1
```

**Nmap**:
```bash
nmap -oX - <scan_args> <hostname>
```

**SSLScan**:
```bash
sslscan --json <hostname>:<port>
```

**Lighthouse** (Local):
```bash
lighthouse <url> --output=json --output-path=<path> --only-categories=performance --preset=desktop
```

### File Locations

- **Tool Execution**: `backend/app/services/tools.py`
- **Scan Orchestration**: `backend/app/services/scan_orchestrator.py`
- **Findings Parsing**: `backend/app/services/findings_ingestor.py`
- **AI Reporting**: `backend/app/services/ai/reporter.py`
- **Scan Profiles**: `backend/app/services/scan_profiles.py`
- **Performance Scanner**: `backend/app/services/performance_scanner.py`
- **PDF Reports**: `backend/app/services/pdf_reports.py`

---

## Summary

### Current State (January 2025)

**Active Tools**: 4 (Nuclei, Nmap, SSLScan, Lighthouse)  
**Supporting Services**: 4 (Orchestrator, Ingestor, Reporter, PDF Generator)  
**Stubbed Features**: 2 (run_nuclei_basic, run_basic_scan_for_job)  
**Placeholder Services**: 2 (AI Adaptive, AI Planner)  
**High Priority TODOs**: 3  
**Medium Priority TODOs**: 4  
**Low Priority TODOs**: 5  

### Next Steps

1. **Immediate**: Complete LLM integration for AI reports
2. **Short-term**: Set up Alembic migrations
3. **Short-term**: Enhance authentication with JWT
4. **Medium-term**: Add monitoring and structured logging
5. **Long-term**: Expand tool suite and Cloud Run integration

---

*This document should be updated whenever tools are added, modified, or deprecated.*  
*Last review date should be updated in the header.*


**Last Updated**: January 2025  
**Purpose**: Track active tools, stubbed features, and future work items

---

## Tool Selection Configuration

**Important**: Tool selection for each scan level is controlled by the **Tool Matrix** in `backend/app/core/tool_matrix.py`. This is the **single source of truth** for which tools run at each scan level.

- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap  
- **Advanced**: Nuclei + Nmap + SSLScan

To modify which tools run at each level, edit `TOOL_MATRIX` in `app/core/tool_matrix.py`. The orchestration code automatically uses this configuration.

**Adding a new tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels
3. Extend the orchestration routing logic if needed (most tools work automatically)
4. Add parsing logic in `app/services/findings_ingestor.py`

---

## Table of Contents
1. [Active Tools](#active-tools)
2. [Stubbed/Placeholder Features](#stubbedplaceholder-features)
3. [Future Work & TODOs](#future-work--todos)
4. [Maintenance Guide](#maintenance-guide)

---

## Active Tools

### ✅ Security Scanning Tools

#### **1. Nuclei (Vulnerability Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nuclei()`
- **Version**: Nuclei v3.4.10
- **Implementation**:
  - Executes via subprocess
  - Supports severity filtering (low, medium, high, critical, info)
  - Uses template tags (cve, vulnerability, exposure, misconfig, etc.)
  - Output format: JSONL (JSON Lines)
  - Rate limiting: 50 requests/second
  - Timeout: 30 minutes per scan
  - Retries: 1 retry on failure
- **Scan Level Configuration**:
  - **Basic**: `low,medium` severity, `cve,vulnerability,exposure` tags
  - **Pro**: `low,medium,high` severity, `cve,vulnerability,exposure,misconfig,default-login` tags
  - **Advanced**: `low,medium,high,critical,info` severity, `cve,vulnerability,exposure,misconfig,default-login,tech,ssl` tags
- **Error Handling**: 
  - Checks if nuclei binary exists before execution
  - Handles timeouts gracefully
  - Distinguishes between "no findings" (success) and actual errors
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nuclei_output()`

#### **2. Nmap (Port Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nmap()`
- **Implementation**:
  - Executes via subprocess
  - Output format: XML (`-oX -`)
  - Timeout: 30 minutes
- **Scan Level Configuration**:
  - **Basic**: `--top-ports 100 -sV` (top 100 ports, version detection)
  - **Pro**: `-sV -sC --top-ports 1000` (version detection, default scripts, top 1000 ports)
  - **Advanced**: `-sV -sC -A -p-` (version detection, default scripts, aggressive, all ports)
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nmap_output()`

#### **3. SSLScan (TLS/SSL Analyzer)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_sslscan()`
- **Implementation**:
  - Executes via subprocess
  - Output format: JSON (`--json`)
  - Timeout: 5 minutes
  - Fallback: Uses `openssl s_client` if sslscan not available
- **Fallback Implementation**: `_run_openssl_fallback()` uses OpenSSL for basic SSL checks
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_sslscan_output()`

### ✅ Performance Scanning Tools

#### **4. Lighthouse (Performance Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/performance_scanner.py`
- **Implementation**:
  - Supports both local and Cloud Run execution
  - Local: Uses subprocess to run `lighthouse` CLI
  - Cloud Run: Calls external Cloud Run service (if configured)
  - Device modes: `desktop` (default), `mobile` (future)
- **Metrics Extracted**:
  - Performance score (0-100)
  - First Contentful Paint (FCP)
  - Largest Contentful Paint (LCP)
  - Time to Interactive (TTI)
  - Cumulative Layout Shift (CLS)
  - First Input Delay (FID)
  - Speed Index
  - Total requests and page size
- **Output Format**: JSON with categories, metrics, opportunities, diagnostics
- **Timeout**: 5 minutes (300 seconds)

### ✅ Supporting Services

#### **5. Scan Orchestrator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/scan_orchestrator.py`
- **Features**:
  - Queues scans via Celery
  - Manages scan execution pipeline
  - Coordinates tool execution
  - Generates AI reports
  - Updates scan status

#### **6. Findings Ingestor**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/findings_ingestor.py`
- **Features**:
  - Parses Nuclei JSONL output
  - Parses Nmap XML output
  - Parses SSLScan JSON/text output
  - Creates Finding records in database
  - Extracts CVE/CWE IDs, CVSS scores, severity

#### **7. AI Reporter**
- **Status**: ⚠️ **PARTIALLY ACTIVE** (Rule-based, LLM TODO)
- **Location**: `backend/app/services/ai/reporter.py`
- **Current Implementation**:
  - Rule-based report generation
  - Generates executive summary
  - Identifies top risks
  - Calculates risk score
  - Creates remediation overview
- **Limitation**: Uses rule-based logic, not LLM (see TODOs)

#### **8. PDF Report Generator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/pdf_reports.py`
- **Features**:
  - Generates branded PDF reports using ReportLab
  - Two modes: `full` (detailed) and `executive` (summary)
  - Sections: Cover, Executive Summary, Network/TLS, Stack Fingerprint, Findings Detail
  - Multi-tenant scoped

---

## Stubbed/Placeholder Features

### ⚠️ Deprecated/Unused Functions

#### **1. `run_nuclei_basic()`**
- **Status**: ❌ **STUB - NOT USED**
- **Location**: `backend/app/services/tools.py:16`
- **Reason**: Replaced by `ToolExecutor._run_nuclei()` which is the active implementation
- **Action**: Can be removed in future cleanup

#### **2. `run_basic_scan_for_job()`**
- **Status**: ❌ **DEPRECATED**
- **Location**: `backend/app/services/scan_orchestrator.py:70`
- **Reason**: Replaced by `run_scan_for_job()` which handles all scan levels
- **Action**: Marked as deprecated, can be removed

### ⚠️ Placeholder Services

#### **3. AI Adaptive Scanner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/adaptive.py`
- **Current State**: 
  - Function `refine_scan()` exists but returns placeholder logic
  - Intended for future adaptive scanning based on stack info
- **Future**: Will analyze stack info and adjust scan strategy dynamically

#### **4. AI Planner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/planner.py`
- **Current State**:
  - Function `plan_scan()` exists but returns basic plan
  - Intended for future intelligent scan planning
- **Future**: Will create custom scan plans based on target characteristics

---

## Future Work & TODOs

### 🔴 High Priority

#### **1. LLM Integration for AI Reports**
- **Status**: ❌ **TODO**
- **Location**: `backend/app/services/ai/reporter.py:89`
- **Current**: Rule-based report generation
- **Needed**:
  - Integrate OpenAI or Anthropic API
  - Generate richer executive summaries
  - Create contextual remediation recommendations
  - Analyze findings for patterns and trends
- **Estimated Effort**: 2-3 days
- **Dependencies**: API keys, LLM service account

#### **2. Enhanced Authentication**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/core/tenant_utils.py`
- **Current**: 
  - Uses header-based authentication (`X-Thandev-User-Id`, `X-Thandev-Tenant-Id`)
  - No JWT validation (structure ready for future)
- **Needed**:
  - JWT token validation
  - Session sync between NextAuth and backend
  - Support for multiple users per tenant (org accounts)
- **Estimated Effort**: 3-5 days

#### **3. Database Migrations**
- **Status**: ❌ **TODO**
- **Location**: Development uses `Base.metadata.create_all()`
- **Current**: Manual schema changes in development
- **Needed**:
  - Set up Alembic migrations
  - Create migration scripts for production
  - Version control for schema changes
- **Estimated Effort**: 1-2 days

### 🟡 Medium Priority

#### **4. Rate Limiting**
- **Status**: ⚠️ **PARTIAL**
- **Location**: Only legacy security router has rate limiting
- **Current**: Plan-based limits (monthly scans, concurrent scans)
- **Needed**:
  - API-level rate limiting (per endpoint)
  - Per-user rate limiting
  - DDoS protection
- **Estimated Effort**: 2-3 days

#### **5. Monitoring & Logging**
- **Status**: ❌ **TODO**
- **Current**: Basic Python logging
- **Needed**:
  - Structured logging (JSON format)
  - Metrics collection (Prometheus)
  - Error tracking (Sentry)
  - Performance monitoring
- **Estimated Effort**: 3-4 days

#### **6. Caching Strategy**
- **Status**: ⚠️ **MINIMAL**
- **Location**: `backend/app/utils/cache.py` exists but minimal usage
- **Current**: Redis configured but underutilized
- **Needed**:
  - Cache RSS feed results (news page)
  - Cache project stats
  - Cache scan results (with TTL)
  - Cache user sessions
- **Estimated Effort**: 2-3 days

#### **7. Performance Scan Enhancements**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/api/performance.py:106`
- **Current**: 
  - Lighthouse integration works
  - Device selection hardcoded to "desktop"
- **Needed**:
  - Device selection based on scan level or user preference
  - Mobile device emulation
  - Network throttling simulation
  - Performance recommendations
- **Estimated Effort**: 2-3 days

### 🟢 Low Priority / Future Enhancements

#### **8. Additional Security Tools**
- **Status**: ❌ **FUTURE**
- **Potential Tools**:
  - **Subfinder/Amass**: Subdomain enumeration
  - **FFuf/Gobuster**: Directory/file discovery
  - **Nikto**: HTTP server vulnerability scanner
  - **SQLMap**: SQL injection testing (with authorization)
- **Estimated Effort**: 5-7 days per tool

#### **9. Cloud Run Integration**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/services/performance_scanner.py:142`
- **Current**: 
  - Performance scans support Cloud Run
  - Security scans use local execution
- **Needed**:
  - Migrate security scans to Cloud Run for scalability
  - Support for distributed scanning
  - Job queue management
- **Estimated Effort**: 5-7 days

#### **10. Advanced AI Features**
- **Status**: ❌ **FUTURE**
- **Features**:
  - Adaptive scanning based on stack info
  - Intelligent scan planning
  - Finding correlation and deduplication
  - Risk prediction
- **Estimated Effort**: 10-15 days

#### **11. Data Enrichment**
- **Status**: ❌ **FUTURE**
- **Location**: `backend/THANDEV_V2_STRUCTURE.md` mentions `ingest_nvd`, `ingest_kev`
- **Needed**:
  - NVD (National Vulnerability Database) integration
  - KEV (Known Exploited Vulnerabilities) integration
  - CVE/CWE metadata enrichment
  - Exploit availability checking
- **Estimated Effort**: 7-10 days

#### **12. Frontend Enhancements**
- **Status**: ⚠️ **ONGOING**
- **Current Gaps**:
  - Toast notifications (currently using alerts)
  - Better loading states (some pages lack skeletons)
  - Empty state handling (some pages need improvement)
  - Error boundaries
- **Estimated Effort**: 3-5 days

---

## Tool Execution Flow

### Current Active Flow

```
1. User creates scan via API
   ↓
2. ScanJob created (status: PENDING)
   ↓
3. Celery task queued (status: QUEUED)
   ↓
4. Celery worker picks up task (status: RUNNING)
   ↓
5. ScanOrchestrator.run_scan_for_job()
   ↓
6. Get scan profile for level (basic/pro/advanced)
   ↓
7. For each tool in profile:
   ├─ ToolExecutor.run_tool()
   ├─ Execute tool via subprocess
   ├─ Save output to data/jobs/{job_id}/{tool}_output.json
   ├─ FindingsIngestor.parse_{tool}_output()
   └─ Create Finding records
   ↓
8. AI Reporter.generate_basic_report()
   ↓
9. Update ScanJob (status: COMPLETED, summary: {...})
```

### Tool Configuration

**Tool Matrix** (`backend/app/core/tool_matrix.py`):
- **Single source of truth** for tool selection per scan level
- Uses `ScanLevel` enum (BASIC, PRO, ADVANCED)
- Defines `TOOL_MATRIX` mapping scan levels to `ToolConfig` lists
- Helper functions: `get_tools_for_level()`, `get_enabled_tool_keys()`, `is_tool_enabled_for_level()`
- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap
- **Advanced**: Nuclei + Nmap + SSLScan

**Scan Profiles** (`backend/app/services/scan_profiles.py`):
- Provides backward-compatible interface
- Now uses `tool_matrix` as the source of truth
- Converts `ToolConfig` to legacy profile format for compatibility

**Tool Executor** (`backend/app/services/tools.py`):
- Supports: `nuclei`, `nmap`, `sslscan`
- Each tool has async `_run_{tool}()` method
- Returns structured result with output, exit_code, command

**Adding a New Tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels in `app/core/tool_matrix.py`
3. Extend the orchestration routing logic in `scan_orchestrator.py` if needed
4. Update this documentation

---

## Maintenance Guide

### How to Keep This Document Updated

#### **When Adding a New Tool**:
1. **Implement the tool runner** in `app/services/tools.py`:
   - Add tool method to `ToolExecutor` (e.g., `_run_newtool()`)
   - Add tool key to `ToolExecutor.supported_tools` dict
   
2. **Add tool to tool matrix** in `app/core/tool_matrix.py`:
   - Add `{"key": "newtool", "enabled": True}` to `TOOL_MATRIX` for desired scan levels
   - This is the **single source of truth** for tool selection
   
3. **Update orchestration** in `app/services/scan_orchestrator.py` if needed:
   - Most tools work automatically via `ToolExecutor.run_tool()`
   - Only add custom routing if tool needs special handling
   
4. **Add parsing logic** in `app/services/findings_ingestor.py`:
   - Create `parse_newtool_output()` function
   - Create `ingest_newtool_findings()` function
   - Follow the same pattern as existing tools
   
5. **Update documentation**:
   - Add tool to "Active Tools" section in this file
   - Document implementation location, configuration, output format
   - Update "Tool Configuration" section

#### **When Marking a Feature as Complete**:
1. Move from "Future Work" to "Active Tools"
2. Update status from ❌ TODO to ✅ ACTIVE
3. Add completion date
4. Document any limitations or known issues

#### **When Deprecating a Feature**:
1. Move to "Stubbed/Placeholder Features"
2. Mark as ❌ DEPRECATED or ⚠️ STUB
3. Document reason for deprecation
4. Note replacement (if any)

#### **When Adding a TODO**:
1. Add to appropriate priority section (High/Medium/Low)
2. Include:
   - Current status
   - Location (file path)
   - What's needed
   - Estimated effort
   - Dependencies
3. Update "Last Updated" date at top

#### **Regular Review Schedule**:
- **Weekly**: Review TODOs and update priorities
- **Monthly**: Review completed work and move to "Active Tools"
- **Quarterly**: Review roadmap and adjust estimates

### Status Indicators

- ✅ **FULLY ACTIVE**: Feature is complete and working in production
- ⚠️ **PARTIALLY ACTIVE**: Feature works but has limitations or TODOs
- ❌ **TODO**: Feature not yet implemented
- 🚧 **IN PROGRESS**: Feature currently being developed
- 🔴 **HIGH PRIORITY**: Should be addressed soon
- 🟡 **MEDIUM PRIORITY**: Important but not urgent
- 🟢 **LOW PRIORITY**: Nice to have, future enhancement

---

## Quick Reference

### Active Tool Commands

**Nuclei**:
```bash
nuclei -u <target_url> -severity <levels> -tags <tags> -jsonl -silent -rate-limit 50 -timeout 10 -retries 1
```

**Nmap**:
```bash
nmap -oX - <scan_args> <hostname>
```

**SSLScan**:
```bash
sslscan --json <hostname>:<port>
```

**Lighthouse** (Local):
```bash
lighthouse <url> --output=json --output-path=<path> --only-categories=performance --preset=desktop
```

### File Locations

- **Tool Execution**: `backend/app/services/tools.py`
- **Scan Orchestration**: `backend/app/services/scan_orchestrator.py`
- **Findings Parsing**: `backend/app/services/findings_ingestor.py`
- **AI Reporting**: `backend/app/services/ai/reporter.py`
- **Scan Profiles**: `backend/app/services/scan_profiles.py`
- **Performance Scanner**: `backend/app/services/performance_scanner.py`
- **PDF Reports**: `backend/app/services/pdf_reports.py`

---

## Summary

### Current State (January 2025)

**Active Tools**: 4 (Nuclei, Nmap, SSLScan, Lighthouse)  
**Supporting Services**: 4 (Orchestrator, Ingestor, Reporter, PDF Generator)  
**Stubbed Features**: 2 (run_nuclei_basic, run_basic_scan_for_job)  
**Placeholder Services**: 2 (AI Adaptive, AI Planner)  
**High Priority TODOs**: 3  
**Medium Priority TODOs**: 4  
**Low Priority TODOs**: 5  

### Next Steps

1. **Immediate**: Complete LLM integration for AI reports
2. **Short-term**: Set up Alembic migrations
3. **Short-term**: Enhance authentication with JWT
4. **Medium-term**: Add monitoring and structured logging
5. **Long-term**: Expand tool suite and Cloud Run integration

---

*This document should be updated whenever tools are added, modified, or deprecated.*  
*Last review date should be updated in the header.*


**Last Updated**: January 2025  
**Purpose**: Track active tools, stubbed features, and future work items

---

## Tool Selection Configuration

**Important**: Tool selection for each scan level is controlled by the **Tool Matrix** in `backend/app/core/tool_matrix.py`. This is the **single source of truth** for which tools run at each scan level.

- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap  
- **Advanced**: Nuclei + Nmap + SSLScan

To modify which tools run at each level, edit `TOOL_MATRIX` in `app/core/tool_matrix.py`. The orchestration code automatically uses this configuration.

**Adding a new tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels
3. Extend the orchestration routing logic if needed (most tools work automatically)
4. Add parsing logic in `app/services/findings_ingestor.py`

---

## Table of Contents
1. [Active Tools](#active-tools)
2. [Stubbed/Placeholder Features](#stubbedplaceholder-features)
3. [Future Work & TODOs](#future-work--todos)
4. [Maintenance Guide](#maintenance-guide)

---

## Active Tools

### ✅ Security Scanning Tools

#### **1. Nuclei (Vulnerability Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nuclei()`
- **Version**: Nuclei v3.4.10
- **Implementation**:
  - Executes via subprocess
  - Supports severity filtering (low, medium, high, critical, info)
  - Uses template tags (cve, vulnerability, exposure, misconfig, etc.)
  - Output format: JSONL (JSON Lines)
  - Rate limiting: 50 requests/second
  - Timeout: 30 minutes per scan
  - Retries: 1 retry on failure
- **Scan Level Configuration**:
  - **Basic**: `low,medium` severity, `cve,vulnerability,exposure` tags
  - **Pro**: `low,medium,high` severity, `cve,vulnerability,exposure,misconfig,default-login` tags
  - **Advanced**: `low,medium,high,critical,info` severity, `cve,vulnerability,exposure,misconfig,default-login,tech,ssl` tags
- **Error Handling**: 
  - Checks if nuclei binary exists before execution
  - Handles timeouts gracefully
  - Distinguishes between "no findings" (success) and actual errors
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nuclei_output()`

#### **2. Nmap (Port Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_nmap()`
- **Implementation**:
  - Executes via subprocess
  - Output format: XML (`-oX -`)
  - Timeout: 30 minutes
- **Scan Level Configuration**:
  - **Basic**: `--top-ports 100 -sV` (top 100 ports, version detection)
  - **Pro**: `-sV -sC --top-ports 1000` (version detection, default scripts, top 1000 ports)
  - **Advanced**: `-sV -sC -A -p-` (version detection, default scripts, aggressive, all ports)
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_nmap_output()`

#### **3. SSLScan (TLS/SSL Analyzer)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/tools.py:_run_sslscan()`
- **Implementation**:
  - Executes via subprocess
  - Output format: JSON (`--json`)
  - Timeout: 5 minutes
  - Fallback: Uses `openssl s_client` if sslscan not available
- **Fallback Implementation**: `_run_openssl_fallback()` uses OpenSSL for basic SSL checks
- **Output Parsing**: Findings parsed by `backend/app/services/findings_ingestor.py:parse_sslscan_output()`

### ✅ Performance Scanning Tools

#### **4. Lighthouse (Performance Scanner)**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/performance_scanner.py`
- **Implementation**:
  - Supports both local and Cloud Run execution
  - Local: Uses subprocess to run `lighthouse` CLI
  - Cloud Run: Calls external Cloud Run service (if configured)
  - Device modes: `desktop` (default), `mobile` (future)
- **Metrics Extracted**:
  - Performance score (0-100)
  - First Contentful Paint (FCP)
  - Largest Contentful Paint (LCP)
  - Time to Interactive (TTI)
  - Cumulative Layout Shift (CLS)
  - First Input Delay (FID)
  - Speed Index
  - Total requests and page size
- **Output Format**: JSON with categories, metrics, opportunities, diagnostics
- **Timeout**: 5 minutes (300 seconds)

### ✅ Supporting Services

#### **5. Scan Orchestrator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/scan_orchestrator.py`
- **Features**:
  - Queues scans via Celery
  - Manages scan execution pipeline
  - Coordinates tool execution
  - Generates AI reports
  - Updates scan status

#### **6. Findings Ingestor**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/findings_ingestor.py`
- **Features**:
  - Parses Nuclei JSONL output
  - Parses Nmap XML output
  - Parses SSLScan JSON/text output
  - Creates Finding records in database
  - Extracts CVE/CWE IDs, CVSS scores, severity

#### **7. AI Reporter**
- **Status**: ⚠️ **PARTIALLY ACTIVE** (Rule-based, LLM TODO)
- **Location**: `backend/app/services/ai/reporter.py`
- **Current Implementation**:
  - Rule-based report generation
  - Generates executive summary
  - Identifies top risks
  - Calculates risk score
  - Creates remediation overview
- **Limitation**: Uses rule-based logic, not LLM (see TODOs)

#### **8. PDF Report Generator**
- **Status**: ✅ **FULLY ACTIVE**
- **Location**: `backend/app/services/pdf_reports.py`
- **Features**:
  - Generates branded PDF reports using ReportLab
  - Two modes: `full` (detailed) and `executive` (summary)
  - Sections: Cover, Executive Summary, Network/TLS, Stack Fingerprint, Findings Detail
  - Multi-tenant scoped

---

## Stubbed/Placeholder Features

### ⚠️ Deprecated/Unused Functions

#### **1. `run_nuclei_basic()`**
- **Status**: ❌ **STUB - NOT USED**
- **Location**: `backend/app/services/tools.py:16`
- **Reason**: Replaced by `ToolExecutor._run_nuclei()` which is the active implementation
- **Action**: Can be removed in future cleanup

#### **2. `run_basic_scan_for_job()`**
- **Status**: ❌ **DEPRECATED**
- **Location**: `backend/app/services/scan_orchestrator.py:70`
- **Reason**: Replaced by `run_scan_for_job()` which handles all scan levels
- **Action**: Marked as deprecated, can be removed

### ⚠️ Placeholder Services

#### **3. AI Adaptive Scanner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/adaptive.py`
- **Current State**: 
  - Function `refine_scan()` exists but returns placeholder logic
  - Intended for future adaptive scanning based on stack info
- **Future**: Will analyze stack info and adjust scan strategy dynamically

#### **4. AI Planner**
- **Status**: ⚠️ **PLACEHOLDER**
- **Location**: `backend/app/services/ai/planner.py`
- **Current State**:
  - Function `plan_scan()` exists but returns basic plan
  - Intended for future intelligent scan planning
- **Future**: Will create custom scan plans based on target characteristics

---

## Future Work & TODOs

### 🔴 High Priority

#### **1. LLM Integration for AI Reports**
- **Status**: ❌ **TODO**
- **Location**: `backend/app/services/ai/reporter.py:89`
- **Current**: Rule-based report generation
- **Needed**:
  - Integrate OpenAI or Anthropic API
  - Generate richer executive summaries
  - Create contextual remediation recommendations
  - Analyze findings for patterns and trends
- **Estimated Effort**: 2-3 days
- **Dependencies**: API keys, LLM service account

#### **2. Enhanced Authentication**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/core/tenant_utils.py`
- **Current**: 
  - Uses header-based authentication (`X-Thandev-User-Id`, `X-Thandev-Tenant-Id`)
  - No JWT validation (structure ready for future)
- **Needed**:
  - JWT token validation
  - Session sync between NextAuth and backend
  - Support for multiple users per tenant (org accounts)
- **Estimated Effort**: 3-5 days

#### **3. Database Migrations**
- **Status**: ❌ **TODO**
- **Location**: Development uses `Base.metadata.create_all()`
- **Current**: Manual schema changes in development
- **Needed**:
  - Set up Alembic migrations
  - Create migration scripts for production
  - Version control for schema changes
- **Estimated Effort**: 1-2 days

### 🟡 Medium Priority

#### **4. Rate Limiting**
- **Status**: ⚠️ **PARTIAL**
- **Location**: Only legacy security router has rate limiting
- **Current**: Plan-based limits (monthly scans, concurrent scans)
- **Needed**:
  - API-level rate limiting (per endpoint)
  - Per-user rate limiting
  - DDoS protection
- **Estimated Effort**: 2-3 days

#### **5. Monitoring & Logging**
- **Status**: ❌ **TODO**
- **Current**: Basic Python logging
- **Needed**:
  - Structured logging (JSON format)
  - Metrics collection (Prometheus)
  - Error tracking (Sentry)
  - Performance monitoring
- **Estimated Effort**: 3-4 days

#### **6. Caching Strategy**
- **Status**: ⚠️ **MINIMAL**
- **Location**: `backend/app/utils/cache.py` exists but minimal usage
- **Current**: Redis configured but underutilized
- **Needed**:
  - Cache RSS feed results (news page)
  - Cache project stats
  - Cache scan results (with TTL)
  - Cache user sessions
- **Estimated Effort**: 2-3 days

#### **7. Performance Scan Enhancements**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/api/performance.py:106`
- **Current**: 
  - Lighthouse integration works
  - Device selection hardcoded to "desktop"
- **Needed**:
  - Device selection based on scan level or user preference
  - Mobile device emulation
  - Network throttling simulation
  - Performance recommendations
- **Estimated Effort**: 2-3 days

### 🟢 Low Priority / Future Enhancements

#### **8. Additional Security Tools**
- **Status**: ❌ **FUTURE**
- **Potential Tools**:
  - **Subfinder/Amass**: Subdomain enumeration
  - **FFuf/Gobuster**: Directory/file discovery
  - **Nikto**: HTTP server vulnerability scanner
  - **SQLMap**: SQL injection testing (with authorization)
- **Estimated Effort**: 5-7 days per tool

#### **9. Cloud Run Integration**
- **Status**: ⚠️ **PARTIAL**
- **Location**: `backend/app/services/performance_scanner.py:142`
- **Current**: 
  - Performance scans support Cloud Run
  - Security scans use local execution
- **Needed**:
  - Migrate security scans to Cloud Run for scalability
  - Support for distributed scanning
  - Job queue management
- **Estimated Effort**: 5-7 days

#### **10. Advanced AI Features**
- **Status**: ❌ **FUTURE**
- **Features**:
  - Adaptive scanning based on stack info
  - Intelligent scan planning
  - Finding correlation and deduplication
  - Risk prediction
- **Estimated Effort**: 10-15 days

#### **11. Data Enrichment**
- **Status**: ❌ **FUTURE**
- **Location**: `backend/THANDEV_V2_STRUCTURE.md` mentions `ingest_nvd`, `ingest_kev`
- **Needed**:
  - NVD (National Vulnerability Database) integration
  - KEV (Known Exploited Vulnerabilities) integration
  - CVE/CWE metadata enrichment
  - Exploit availability checking
- **Estimated Effort**: 7-10 days

#### **12. Frontend Enhancements**
- **Status**: ⚠️ **ONGOING**
- **Current Gaps**:
  - Toast notifications (currently using alerts)
  - Better loading states (some pages lack skeletons)
  - Empty state handling (some pages need improvement)
  - Error boundaries
- **Estimated Effort**: 3-5 days

---

## Tool Execution Flow

### Current Active Flow

```
1. User creates scan via API
   ↓
2. ScanJob created (status: PENDING)
   ↓
3. Celery task queued (status: QUEUED)
   ↓
4. Celery worker picks up task (status: RUNNING)
   ↓
5. ScanOrchestrator.run_scan_for_job()
   ↓
6. Get scan profile for level (basic/pro/advanced)
   ↓
7. For each tool in profile:
   ├─ ToolExecutor.run_tool()
   ├─ Execute tool via subprocess
   ├─ Save output to data/jobs/{job_id}/{tool}_output.json
   ├─ FindingsIngestor.parse_{tool}_output()
   └─ Create Finding records
   ↓
8. AI Reporter.generate_basic_report()
   ↓
9. Update ScanJob (status: COMPLETED, summary: {...})
```

### Tool Configuration

**Tool Matrix** (`backend/app/core/tool_matrix.py`):
- **Single source of truth** for tool selection per scan level
- Uses `ScanLevel` enum (BASIC, PRO, ADVANCED)
- Defines `TOOL_MATRIX` mapping scan levels to `ToolConfig` lists
- Helper functions: `get_tools_for_level()`, `get_enabled_tool_keys()`, `is_tool_enabled_for_level()`
- **Basic**: Nuclei only
- **Pro**: Nuclei + Nmap
- **Advanced**: Nuclei + Nmap + SSLScan

**Scan Profiles** (`backend/app/services/scan_profiles.py`):
- Provides backward-compatible interface
- Now uses `tool_matrix` as the source of truth
- Converts `ToolConfig` to legacy profile format for compatibility

**Tool Executor** (`backend/app/services/tools.py`):
- Supports: `nuclei`, `nmap`, `sslscan`
- Each tool has async `_run_{tool}()` method
- Returns structured result with output, exit_code, command

**Adding a New Tool**:
1. Implement the tool runner in `app/services/tools.py` (add to `ToolExecutor.supported_tools`)
2. Add a `ToolConfig` entry in `TOOL_MATRIX` for the desired scan levels in `app/core/tool_matrix.py`
3. Extend the orchestration routing logic in `scan_orchestrator.py` if needed
4. Update this documentation

---

## Maintenance Guide

### How to Keep This Document Updated

#### **When Adding a New Tool**:
1. **Implement the tool runner** in `app/services/tools.py`:
   - Add tool method to `ToolExecutor` (e.g., `_run_newtool()`)
   - Add tool key to `ToolExecutor.supported_tools` dict
   
2. **Add tool to tool matrix** in `app/core/tool_matrix.py`:
   - Add `{"key": "newtool", "enabled": True}` to `TOOL_MATRIX` for desired scan levels
   - This is the **single source of truth** for tool selection
   
3. **Update orchestration** in `app/services/scan_orchestrator.py` if needed:
   - Most tools work automatically via `ToolExecutor.run_tool()`
   - Only add custom routing if tool needs special handling
   
4. **Add parsing logic** in `app/services/findings_ingestor.py`:
   - Create `parse_newtool_output()` function
   - Create `ingest_newtool_findings()` function
   - Follow the same pattern as existing tools
   
5. **Update documentation**:
   - Add tool to "Active Tools" section in this file
   - Document implementation location, configuration, output format
   - Update "Tool Configuration" section

#### **When Marking a Feature as Complete**:
1. Move from "Future Work" to "Active Tools"
2. Update status from ❌ TODO to ✅ ACTIVE
3. Add completion date
4. Document any limitations or known issues

#### **When Deprecating a Feature**:
1. Move to "Stubbed/Placeholder Features"
2. Mark as ❌ DEPRECATED or ⚠️ STUB
3. Document reason for deprecation
4. Note replacement (if any)

#### **When Adding a TODO**:
1. Add to appropriate priority section (High/Medium/Low)
2. Include:
   - Current status
   - Location (file path)
   - What's needed
   - Estimated effort
   - Dependencies
3. Update "Last Updated" date at top

#### **Regular Review Schedule**:
- **Weekly**: Review TODOs and update priorities
- **Monthly**: Review completed work and move to "Active Tools"
- **Quarterly**: Review roadmap and adjust estimates

### Status Indicators

- ✅ **FULLY ACTIVE**: Feature is complete and working in production
- ⚠️ **PARTIALLY ACTIVE**: Feature works but has limitations or TODOs
- ❌ **TODO**: Feature not yet implemented
- 🚧 **IN PROGRESS**: Feature currently being developed
- 🔴 **HIGH PRIORITY**: Should be addressed soon
- 🟡 **MEDIUM PRIORITY**: Important but not urgent
- 🟢 **LOW PRIORITY**: Nice to have, future enhancement

---

## Quick Reference

### Active Tool Commands

**Nuclei**:
```bash
nuclei -u <target_url> -severity <levels> -tags <tags> -jsonl -silent -rate-limit 50 -timeout 10 -retries 1
```

**Nmap**:
```bash
nmap -oX - <scan_args> <hostname>
```

**SSLScan**:
```bash
sslscan --json <hostname>:<port>
```

**Lighthouse** (Local):
```bash
lighthouse <url> --output=json --output-path=<path> --only-categories=performance --preset=desktop
```

### File Locations

- **Tool Execution**: `backend/app/services/tools.py`
- **Scan Orchestration**: `backend/app/services/scan_orchestrator.py`
- **Findings Parsing**: `backend/app/services/findings_ingestor.py`
- **AI Reporting**: `backend/app/services/ai/reporter.py`
- **Scan Profiles**: `backend/app/services/scan_profiles.py`
- **Performance Scanner**: `backend/app/services/performance_scanner.py`
- **PDF Reports**: `backend/app/services/pdf_reports.py`

---

## Summary

### Current State (January 2025)

**Active Tools**: 4 (Nuclei, Nmap, SSLScan, Lighthouse)  
**Supporting Services**: 4 (Orchestrator, Ingestor, Reporter, PDF Generator)  
**Stubbed Features**: 2 (run_nuclei_basic, run_basic_scan_for_job)  
**Placeholder Services**: 2 (AI Adaptive, AI Planner)  
**High Priority TODOs**: 3  
**Medium Priority TODOs**: 4  
**Low Priority TODOs**: 5  

### Next Steps

1. **Immediate**: Complete LLM integration for AI reports
2. **Short-term**: Set up Alembic migrations
3. **Short-term**: Enhance authentication with JWT
4. **Medium-term**: Add monitoring and structured logging
5. **Long-term**: Expand tool suite and Cloud Run integration

---

*This document should be updated whenever tools are added, modified, or deprecated.*  
*Last review date should be updated in the header.*

