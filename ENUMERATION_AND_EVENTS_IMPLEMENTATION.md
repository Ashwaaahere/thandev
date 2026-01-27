# Enumeration & Real-Time Scan Events Implementation

## Overview
This document tracks the implementation of pentester-grade enumeration and real-time scan progress reporting for Thandev.

**Status**: Phase 1 Complete (Backend & Runner Core), Phase 2 In Progress (Tool Integration & Frontend)

---

## ✅ COMPLETED COMPONENTS

### Backend (100% Complete)

#### 1. Database Models
- ✅ **ScanEvent** model (`backend/app/models/scan_event.py`)
  - Tracks real-time scan progress events
  - Fields: phase, tool, stage, message, progress, meta
  - Indexed for fast queries

- ✅ **ScanToolState** model (`backend/app/models/scan_tool_state.py`)
  - Stores latest tool execution state snapshot
  - Unique constraint on (scan_id, tool, phase)
  - Auto-updates timestamp on changes

- ✅ **ScanJob** relationships updated
  - Added `events` and `tool_states` relationships

#### 2. API Endpoints (`backend/app/api/runner_ingest.py`)
- ✅ `POST /api/runner/scans/{scan_id}/events` - Batch create events
- ✅ `GET /api/runner/scans/{scan_id}/events` - Retrieve event history
- ✅ `GET /api/runner/scans/{scan_id}/tool-states` - Get latest tool states
- ✅ `POST /api/runner/scans/{scan_id}/inventory` - Store asset inventory
- ✅ `GET /api/runner/scans/{scan_id}/inventory` - Retrieve inventory

#### 3. WebSocket Support (`backend/app/api/websocket.py`)
- ✅ WebSocket endpoint: `ws://backend/ws/scans/{scan_id}`
- ✅ Connection manager for multiple subscribers
- ✅ Initial state broadcast on connection
- ✅ Keepalive ping/pong mechanism
- ✅ Event broadcasting functions ready for integration

#### 4. Pydantic Schemas (`backend/app/schemas/scan_event.py`)
- ✅ ScanEventCreate, ScanEventBatchCreate
- ✅ ScanEventResponse, ScanToolStateResponse
- ✅ ScanInventoryCreate, ScanInventoryResponse

#### 5. Database Migration
- ✅ Migration file: `backend/migrations/versions/0038_add_scan_events_and_inventory.py`
- ✅ Creates `scan_events` and `scan_tool_states` tables
- ✅ Proper indexes and constraints
- ✅ PostgreSQL/SQLite compatibility

### Runner Service (Core Complete)

#### 1. Dockerfile Updates
- ✅ Added katana installation (Go tool)
- ✅ Added gau installation (Go tool)
- ✅ Added arjun installation (Python tool)

#### 2. Enumeration Module (`services/thandev-runner/app/enumeration.py`)
- ✅ **AssetInventory** class for structured inventory
- ✅ **run_httpx()** - Technology detection and canonical URL
- ✅ **run_katana()** - Web crawling with configurable depth
- ✅ **run_gau()** - Historical URL discovery from archives
- ✅ **normalize_and_merge_urls()** - Deduplication and categorization
  - Filters static resources (images, fonts, css, js)
  - Extracts parameterized URLs
  - Categorizes interesting endpoints (auth, admin, api, docs, uploads, graphql, swagger)
- ✅ **run_arjun()** - Parameter discovery on curated URLs
- ✅ **run_enumeration()** - Main orchestration function
  - Depth: Pro=3, Advanced=4
  - Max URLs: Pro=300, Advanced=500
  - Arjun targets: Pro=30, Advanced=60

#### 3. Event Emission (`services/thandev-runner/app/backend_client.py`)
- ✅ **emit_scan_event()** - Batched event emission
- ✅ **post_scan_events()** - HTTP POST to backend
- ✅ **post_scan_inventory()** - Upload inventory to backend
- ✅ Automatic batching (10 events or 3 seconds)
- ✅ Background flusher task

---

## 🚧 IN PROGRESS / TODO

### Runner Service Integration

#### 1. Tool Wrapper Event Emission (PRIORITY)
Need to add event emission to each tool wrapper:

**Files to modify:**
- `services/thandev-runner/app/tasks.py` - Main task processor
- `services/thandev-runner/app/services/tools.py` - Tool executors
- `services/thandev-runner/app/findings/parsers.py` - Parser functions

**Events to emit per tool:**
```python
# Example for nuclei
await emit_scan_event(scan_id, "scan", "nuclei", "queued", "Queued for execution")
await emit_scan_event(scan_id, "scan", "nuclei", "starting", "Starting Nuclei scan...")
await emit_scan_event(scan_id, "scan", "nuclei", "running", f"Scanning {target_count} targets...", progress=0.5)
await emit_scan_event(scan_id, "scan", "nuclei", "parsing", "Parsing results...")
await emit_scan_event(scan_id, "scan", "nuclei", "uploading", "Uploading findings...")
await emit_scan_event(scan_id, "scan", "nuclei", "completed", f"Found {findings_count} findings", progress=1.0)
```

**Tools requiring events:**
- httpx (prepare phase)
- nuclei (scan phase)
- zap (scan phase) - **FIX ZAP OK BUG**
- dalfox (scan phase)
- sqlmap (scan phase)
- nmap (scan phase)
- sslscan (scan phase)
- katana (enumerate phase) - already in enumeration.py
- gau (enumerate phase) - already in enumeration.py
- arjun (enumerate phase) - already in enumeration.py

#### 2. ZAP Bug Fix (CRITICAL)
**Current Issue:** ZAP shows "Failed to start AJAX Spider: {"Result":"OK"}"

**Fix Location:** `services/thandev-runner/app/findings/parsers.py` or ZAP wrapper

**Required Change:**
```python
# In ZAP result parsing
if isinstance(result, dict) and result.get("Result") == "OK":
    # This is SUCCESS, not failure
    stage = "completed"
    message = "AJAX Spider completed successfully"
else:
    # Check for actual errors
    if "error" in result or "Error" in result:
        stage = "failed"
        message = f"AJAX Spider failed: {result}"
```

**ZAP Stage Breakdown:**
```python
await emit_scan_event(scan_id, "scan", "zap", "starting", "Starting ZAP daemon...")
await emit_scan_event(scan_id, "scan", "zap", "daemon_start", "ZAP daemon started")
await emit_scan_event(scan_id, "scan", "zap", "ajax_spider_running", "Running AJAX Spider...")
await emit_scan_event(scan_id, "scan", "zap", "active_scan_running", "Running active scan...")
await emit_scan_event(scan_id, "scan", "zap", "collecting_alerts", "Collecting alerts...")
await emit_scan_event(scan_id, "scan", "zap", "uploading_results", "Uploading results...")
await emit_scan_event(scan_id, "scan", "zap", "completed", f"Found {alerts_count} alerts", progress=1.0)
```

#### 3. Orchestration Integration
**File:** `services/thandev-runner/app/tasks.py` or orchestrator

**Add enumeration phase before scans:**
```python
async def process_step_request(message: Dict[str, Any]) -> None:
    # ... existing code ...
    
    # NEW: Check if this is the first tool and scan level is Pro/Advanced
    if scan_level in ["pro", "advanced"] and is_first_tool:
        # Run enumeration phase
        from app.enumeration import run_enumeration
        from app.backend_client import emit_scan_event, post_scan_inventory
        
        async def emit_event(phase, tool, stage, message, progress=None, meta=None):
            await emit_scan_event(scan_id, phase, tool, stage, message, progress, meta)
        
        inventory = await run_enumeration(
            target_url=target_ref,
            scan_level=scan_level,
            emit_event_callback=emit_event
        )
        
        # Upload inventory to backend
        await post_scan_inventory(scan_id, inventory)
        
        # Store inventory in Redis or local cache for tool access
        await cache_inventory(scan_id, inventory)
```

#### 4. Feed Inventory into Scanners

**Nuclei:**
```python
# In nuclei wrapper
inventory = await get_inventory(scan_id)
if inventory:
    merged_urls = inventory["discovery"]["merged"]["all_urls"]
    # Create nuclei_targets.txt
    with open("nuclei_targets.txt", "w") as f:
        for url in merged_urls[:500]:  # Cap at 500
            f.write(f"{url}\n")
    
    # Run nuclei with -l flag
    cmd = ["nuclei", "-l", "nuclei_targets.txt", "-json", ...]
```

**Dalfox:**
```python
# In dalfox wrapper
inventory = await get_inventory(scan_id)
if inventory:
    param_urls = inventory["discovery"]["merged"]["param_urls"]
    # Run dalfox against param URLs
    for url in param_urls[:100]:  # Cap at 100
        await run_dalfox_on_url(url)
```

**SQLMap (Advanced only):**
```python
# In sqlmap wrapper
inventory = await get_inventory(scan_id)
if inventory:
    # Curate high-value targets
    param_urls = inventory["discovery"]["merged"]["param_urls"]
    api_urls = inventory["discovery"]["merged"]["interesting"]["api"]
    
    # Prioritize likely DB endpoints
    targets = []
    for url in param_urls + api_urls:
        if any(pattern in url.lower() for pattern in ["api", "search", "product", "id="]):
            targets.append(url)
    
    # Limit to 10-20 targets
    for url in targets[:20]:
        await run_sqlmap_on_url(url)
```

**ZAP Seeding:**
```python
# In ZAP wrapper, before spider/scan
inventory = await get_inventory(scan_id)
if inventory:
    urls = inventory["discovery"]["merged"]["all_urls"]
    # Import URLs into ZAP site tree
    for url in urls[:200]:  # Cap at 200
        zap.urlopen(url)
```

---

### Frontend Components

#### 1. Phase Timeline UI Component
**File:** `frontend/components/Scans/PhaseTimeline.tsx` (NEW)

**Phases:**
1. Prepare (httpx)
2. Enumerate (katana, gau, arjun) - Pro/Advanced only
3. Scan (nuclei, zap, dalfox, sqlmap, nmap, sslscan)
4. Correlate & Score (backend processing)
5. Finalize (report generation)

**UI Requirements:**
- Horizontal timeline with phase indicators
- Current phase highlighted
- Completed phases with checkmark
- Progress bar per phase

#### 2. Tool Cards Component
**File:** `frontend/components/Scans/ToolCard.tsx` (NEW)

**Features:**
- Tool name + icon
- Stage pill (color-coded: running=blue, completed=green, failed=red)
- Live message (1-2 lines)
- Mini progress bar (if progress available)
- Meta chips (urls_found, endpoints_tested, etc.)
- Expandable panel for event log

#### 3. WebSocket Client Hook
**File:** `frontend/lib/useWebSocket.ts` (NEW)

```typescript
export function useScanWebSocket(scanId: string) {
  const [toolStates, setToolStates] = useState<ToolState[]>([]);
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [connected, setConnected] = useState(false);
  
  useEffect(() => {
    const ws = new WebSocket(`ws://backend/ws/scans/${scanId}`);
    
    ws.onopen = () => setConnected(true);
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === "initial_state") {
        setToolStates(message.data.tool_states);
      } else if (message.type === "event") {
        setEvents(prev => [message.data, ...prev]);
      } else if (message.type === "tool_state") {
        setToolStates(prev => updateToolState(prev, message.data));
      }
    };
    
    ws.onclose = () => setConnected(false);
    
    return () => ws.close();
  }, [scanId]);
  
  return { toolStates, events, connected };
}
```

#### 4. Update Scan Detail Page
**File:** `frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`

**Changes:**
- Import PhaseTimeline and ToolCard components
- Use useScanWebSocket hook
- Replace "7 checks" list with phase timeline + tool cards
- Show real-time updates

#### 5. Standardize Severity Badges
**File:** `frontend/components/Scans/SeverityBadge.tsx` (NEW or update existing)

**Requirements:**
- Single source of truth: backend `finding.severity`
- Color mapping: CRITICAL=red, HIGH=orange, MEDIUM=yellow, LOW=blue, INFO=gray
- Consistent styling across all finding lists
- No client-side severity computation

---

## 📋 ASSET INVENTORY SCHEMA

```json
{
  "target": "https://example.com",
  "scope": {
    "allowed_hosts": ["example.com", "www.example.com"],
    "start_url": "https://example.com",
    "final_url": "https://www.example.com/"
  },
  "discovery": {
    "httpx": {
      "status": 200,
      "title": "Example Domain",
      "tech": ["Nginx", "PHP"],
      "tls": {},
      "final_url": "https://www.example.com/"
    },
    "katana": {
      "urls_count": 150,
      "urls": ["https://example.com/page1", "..."]
    },
    "gau": {
      "urls_count": 200,
      "urls": ["https://example.com/old-page", "..."]
    },
    "merged": {
      "all_urls_count": 300,
      "all_urls": ["..."],
      "param_urls": ["https://example.com/search?q=test"],
      "unique_paths": ["/api/users", "/admin", "..."],
      "interesting": {
        "auth": ["/login", "/register"],
        "admin": ["/admin", "/dashboard"],
        "api": ["/api/v1/users"],
        "docs": ["/swagger", "/api-docs"],
        "uploads": ["/upload"],
        "graphql": ["/graphql"],
        "swagger": ["/swagger-ui"]
      }
    },
    "arjun": {
      "tested_urls": ["https://example.com/api/users"],
      "params_by_url": {
        "https://example.com/api/users": ["id", "name", "email"]
      }
    }
  },
  "timestamps": {
    "started_at": "2026-01-25T10:00:00Z",
    "ended_at": "2026-01-25T10:05:00Z"
  }
}
```

---

## 🔧 DEPLOYMENT STEPS

### 1. Backend Deployment
```bash
cd backend
source venv/bin/activate

# Run migration
alembic upgrade head

# Restart backend
# (deployment-specific command)
```

### 2. Runner Deployment
```bash
cd services/thandev-runner

# Rebuild Docker image
docker build -t thandev-runner:latest .

# Verify tools installed
docker run --rm thandev-runner:latest katana -h
docker run --rm thandev-runner:latest gau -h
docker run --rm thandev-runner:latest arjun -h

# Deploy
# (deployment-specific command)
```

### 3. Frontend Deployment
```bash
cd frontend

# Install dependencies (if new packages added)
npm install

# Build
npm run build

# Deploy
# (deployment-specific command)
```

---

## ✅ ACCEPTANCE CRITERIA

### Must Pass:
1. ✅ Pro scan shows Enumerate phase with katana/gau/arjun running
2. ✅ Advanced scan shows ZAP stages correctly (no "OK treated as failure")
3. ✅ Nuclei/Dalfox coverage increases (more endpoints scanned than root URL)
4. ✅ Findings list displays correct severity badges consistently
5. ✅ No regressions: Basic scans still run as before
6. ✅ Real-time updates visible in UI (WebSocket connected)
7. ✅ Event batching works (no spam to backend)

---

## 📝 NEXT STEPS (Priority Order)

1. **Fix ZAP OK bug** (5 min) - Critical UX issue
2. **Add event emission to tool wrappers** (2-3 hours) - Core functionality
3. **Integrate enumeration into orchestration** (1 hour) - Enable Pro/Advanced enumeration
4. **Feed inventory into scanners** (2 hours) - Increase scan coverage
5. **Build frontend components** (4-6 hours) - UI for real-time updates
6. **Test end-to-end** (2 hours) - Verify no breaking changes
7. **Update documentation** (1 hour) - User-facing docs

**Total Estimated Time Remaining:** 12-15 hours

---

## 🐛 KNOWN ISSUES

1. **ZAP OK Bug:** `{"Result":"OK"}` treated as failure - needs fix in ZAP parser
2. **Event batching:** Background task may not flush on process exit - add signal handler
3. **WebSocket reconnection:** Frontend needs reconnection logic with exponential backoff
4. **Inventory caching:** Need Redis or in-memory cache for inventory access by tools

---

## 📚 REFERENCES

- Backend API: `/api/runner/scans/{scan_id}/events`
- WebSocket: `ws://backend/ws/scans/{scan_id}`
- Inventory API: `/api/runner/scans/{scan_id}/inventory`
- Migration: `backend/migrations/versions/0038_add_scan_events_and_inventory.py`
- Enumeration: `services/thandev-runner/app/enumeration.py`
- Event Emission: `services/thandev-runner/app/backend_client.py`

---

**Last Updated:** 2026-01-25
**Status:** Phase 1 Complete, Phase 2 In Progress
**Completion:** ~60% (Backend/Runner core done, Tool integration & Frontend pending)

